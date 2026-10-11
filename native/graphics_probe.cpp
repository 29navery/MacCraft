// MacCraft's experimental ANGLE/Metal preflight. No Minecraft code is needed.
#include <dlfcn.h>
#include <array>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>

using Display = void*;
using Config = void*;
using Context = void*;
using Surface = void*;
using Bool = unsigned;
using Int = int;
constexpr Int NONE = 0x3038;

class Probe {
    void *egl = nullptr, *gles = nullptr;
    Display display = nullptr;
    Surface surface = nullptr;
    Context context = nullptr;
    Bool (*terminate)(Display) = nullptr;
    Bool (*destroySurface)(Display, Surface) = nullptr;
    Bool (*destroyContext)(Display, Context) = nullptr;
    Bool (*makeCurrent)(Display, Surface, Surface, Context) = nullptr;

    template<typename T> T symbol(void* lib, const char* name) {
        auto address = dlsym(lib, name);
        if (!address) throw std::runtime_error(std::string("Missing driver function: ") + name);
        return reinterpret_cast<T>(address);
    }
    void shader(unsigned shader, const char* source,
                void (*shaderSource)(unsigned, int, const char* const*, const int*),
                void (*compile)(unsigned), void (*getiv)(unsigned, unsigned, int*),
                void (*getlog)(unsigned, int, int*, char*)) {
        shaderSource(shader, 1, &source, nullptr);
        compile(shader);
        int ok = 0;
        getiv(shader, 0x8b81, &ok); // GL_COMPILE_STATUS
        if (!ok) {
            std::array<char, 4096> log{};
            getlog(shader, static_cast<int>(log.size()), nullptr, log.data());
            throw std::runtime_error(std::string("Shader translation failed: ") + log.data());
        }
    }
public:
    ~Probe() {
        if (display) {
            if (makeCurrent) makeCurrent(display, nullptr, nullptr, nullptr);
            if (context && destroyContext) destroyContext(display, context);
            if (surface && destroySurface) destroySurface(display, surface);
            if (terminate) terminate(display);
        }
        if (gles) dlclose(gles);
        if (egl) dlclose(egl);
    }
    void run(const std::filesystem::path& directory, int minor) {
        const auto eglPath = directory / "libEGL.dylib";
        const auto glesPath = directory / "libGLESv2.dylib";
        egl = dlopen(eglPath.c_str(), RTLD_NOW | RTLD_LOCAL);
        if (!egl) throw std::runtime_error(std::string("Cannot load ARM64 EGL driver: ") + dlerror());
        gles = dlopen(glesPath.c_str(), RTLD_NOW | RTLD_LOCAL);
        if (!gles) throw std::runtime_error(std::string("Cannot load ARM64 GLES driver: ") + dlerror());
#define EGL_FN(type, name) auto name = symbol<type>(egl, #name)
#define GL_FN(type, name) auto name = symbol<type>(gles, #name)
        EGL_FN(void* (*)(const char*), eglGetProcAddress);
        auto getPlatform = reinterpret_cast<Display (*)(unsigned, void*, const Int*)>(
            eglGetProcAddress("eglGetPlatformDisplayEXT"));
        if (!getPlatform) throw std::runtime_error("ANGLE platform display extension is missing");
        // EGL_PLATFORM_ANGLE_ANGLE, EGL_PLATFORM_ANGLE_TYPE_ANGLE, TYPE_METAL_ANGLE.
        const Int displayAttrs[] = {0x3203, 0x3489, NONE};
        display = getPlatform(0x3202, nullptr, displayAttrs);
        if (!display) throw std::runtime_error("ANGLE could not create a Metal display");
        EGL_FN(Bool (*)(Display, Int*, Int*), eglInitialize);
        terminate = symbol<decltype(terminate)>(egl, "eglTerminate");
        destroySurface = symbol<decltype(destroySurface)>(egl, "eglDestroySurface");
        destroyContext = symbol<decltype(destroyContext)>(egl, "eglDestroyContext");
        makeCurrent = symbol<decltype(makeCurrent)>(egl, "eglMakeCurrent");
        Int major = 0, eglMinor = 0;
        if (!eglInitialize(display, &major, &eglMinor)) throw std::runtime_error("Metal EGL initialization failed");
        EGL_FN(Bool (*)(unsigned), eglBindAPI);
        EGL_FN(Bool (*)(Display, const Int*, Config*, Int, Int*), eglChooseConfig);
        EGL_FN(Surface (*)(Display, Config, const Int*), eglCreatePbufferSurface);
        EGL_FN(Context (*)(Display, Config, Context, const Int*), eglCreateContext);
        if (!eglBindAPI(0x30a0)) throw std::runtime_error("Cannot bind OpenGL ES");
        const Int configAttrs[] = {0x3033, 1, 0x3040, 0x40, 0x3024, 8,
                                  0x3023, 8, 0x3022, 8, 0x3021, 8, NONE};
        Config config = nullptr;
        Int count = 0;
        if (!eglChooseConfig(display, configAttrs, &config, 1, &count) || count != 1)
            throw std::runtime_error("No GLES3 pbuffer configuration");
        const Int surfaceAttrs[] = {0x3057, 16, 0x3056, 16, NONE};
        surface = eglCreatePbufferSurface(display, config, surfaceAttrs);
        // EGL_CONTEXT_MAJOR_VERSION_KHR / EGL_CONTEXT_MINOR_VERSION_KHR.
        const Int contextAttrs[] = {0x3098, 3, 0x30fb, minor, NONE};
        context = eglCreateContext(display, config, nullptr, contextAttrs);
        if (!surface || !context || !makeCurrent(display, surface, surface, context))
            throw std::runtime_error("Metal cannot create the requested GLES 3." + std::to_string(minor) + " context");
        GL_FN(const unsigned char* (*)(unsigned), glGetString);
        const auto rendererPtr = glGetString(0x1f01);
        const auto versionPtr = glGetString(0x1f02);
        if (!rendererPtr || !versionPtr) throw std::runtime_error("Driver returned no renderer/version");
        const std::string renderer(reinterpret_cast<const char*>(rendererPtr));
        const std::string version(reinterpret_cast<const char*>(versionPtr));
        if (renderer.find("Metal") == std::string::npos)
            throw std::runtime_error("Driver is not using Metal: " + renderer);
        GL_FN(void (*)(unsigned, Int*), glGetIntegerv);
        Int glMajor = 0, glMinor = 0;
        glGetIntegerv(0x821b, &glMajor);
        glGetIntegerv(0x821c, &glMinor);
        if (glMajor < 3 || (glMajor == 3 && glMinor < minor))
            throw std::runtime_error("Driver did not provide the requested GLES version");
        GL_FN(unsigned (*)(unsigned), glCreateShader);
        GL_FN(void (*)(unsigned, int, const char* const*, const int*), glShaderSource);
        GL_FN(void (*)(unsigned), glCompileShader);
        GL_FN(void (*)(unsigned, unsigned, int*), glGetShaderiv);
        GL_FN(void (*)(unsigned, int, int*, char*), glGetShaderInfoLog);
        GL_FN(unsigned (*)(), glCreateProgram);
        GL_FN(void (*)(unsigned, unsigned), glAttachShader);
        GL_FN(void (*)(unsigned), glLinkProgram);
        GL_FN(void (*)(unsigned, unsigned, int*), glGetProgramiv);
        GL_FN(void (*)(unsigned, int, int*, char*), glGetProgramInfoLog);
        GL_FN(void (*)(unsigned), glUseProgram);
        GL_FN(void (*)(int, int, int, int), glViewport);
        GL_FN(void (*)(float, float, float, float), glClearColor);
        GL_FN(void (*)(unsigned), glClear);
        GL_FN(void (*)(unsigned, int, int), glDrawArrays);
        GL_FN(void (*)(int, int, int, int, unsigned, unsigned, void*), glReadPixels);
        GL_FN(unsigned (*)(), glGetError);
        GL_FN(void (*)(unsigned), glDeleteShader);
        GL_FN(void (*)(unsigned), glDeleteProgram);
        const auto vertex = glCreateShader(0x8b31), fragment = glCreateShader(0x8b30);
        shader(vertex, "#version 300 es\nconst vec2 p[3]=vec2[3](vec2(-1,-1),vec2(3,-1),vec2(-1,3));\nvoid main(){gl_Position=vec4(p[gl_VertexID],0,1);}",
               glShaderSource, glCompileShader, glGetShaderiv, glGetShaderInfoLog);
        shader(fragment, "#version 300 es\nprecision highp float;\nout vec4 color;\nvoid main(){color=vec4(1,0,0,1);}",
               glShaderSource, glCompileShader, glGetShaderiv, glGetShaderInfoLog);
        const auto program = glCreateProgram();
        glAttachShader(program, vertex);
        glAttachShader(program, fragment);
        glLinkProgram(program);
        int linked = 0;
        glGetProgramiv(program, 0x8b82, &linked);
        if (!linked) {
            std::array<char, 4096> log{};
            glGetProgramInfoLog(program, static_cast<int>(log.size()), nullptr, log.data());
            throw std::runtime_error(std::string("Program translation failed: ") + log.data());
        }
        glUseProgram(program);
        glViewport(0, 0, 16, 16);
        glClearColor(0, 0, 1, 1);
        glClear(0x4000);
        glDrawArrays(4, 0, 3);
        std::array<unsigned char, 4> pixel{};
        glReadPixels(8, 8, 1, 1, 0x1908, 0x1401, pixel.data());
        if (glGetError() || pixel[0] < 240 || pixel[1] > 10 || pixel[2] > 10)
            throw std::runtime_error("Metal shader draw/readback verification failed");
        glDeleteProgram(program);
        glDeleteShader(vertex);
        glDeleteShader(fragment);
        std::cout << "PASS: " << renderer << "\n" << version
                  << "\nGLES shader translation, draw, and pixel readback verified.\n";
    }
};

int main(int argc, char** argv) {
    if (argc < 2 || argc > 3 || (argc == 3 && std::string(argv[2]) != "3.0" && std::string(argv[2]) != "3.1")) {
        std::cerr << "Usage: maccraft-graphics-probe ANGLE_LIBRARY_DIRECTORY [3.0|3.1]\n";
        return 2;
    }
    try {
        Probe probe;
        probe.run(std::filesystem::absolute(argv[1]), argc == 3 && std::string(argv[2]) == "3.1" ? 1 : 0);
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Graphics preflight failed: " << error.what() << '\n';
        return 1;
    }
}
