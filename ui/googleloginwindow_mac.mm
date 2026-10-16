#include <googleloginwindow.h>
#include <QVBoxLayout>
#include <QLabel>
#include <QPushButton>
#include <functional>
#import <AppKit/AppKit.h>
#import <WebKit/WebKit.h>

@interface MacCraftGoogleBrowser : NSObject <WKNavigationDelegate, WKHTTPCookieStoreObserver, WKScriptMessageHandler> {
@public
    std::function<void(NSString*, NSString*, NSString*)> completion;
    std::function<void(NSString*)> failure;
}
@property(nonatomic, weak) WKWebView* webView;
@property(nonatomic) BOOL completed;
@property(nonatomic) BOOL finishRequested;
@property(nonatomic, copy) NSString* email;
- (void)checkCookies;
@end

@implementation MacCraftGoogleBrowser
- (void)checkCookies {
    [self.webView.configuration.websiteDataStore.httpCookieStore getAllCookies:^(NSArray<NSHTTPCookie*>* cookies) {
        NSString* token = nil;
        NSString* userId = nil;
        for(NSHTTPCookie* cookie in cookies) {
            if(![@[@".google.com", @"google.com", @"accounts.google.com", @".accounts.google.com"] containsObject:cookie.domain]) continue;
            if([cookie.name isEqualToString:@"oauth_token"]) token = cookie.value;
            if([cookie.name isEqualToString:@"user_id"]) userId = cookie.value;
        }
        if(self.finishRequested && !self.completed && token.length && userId.length && self->completion) {
            self.completed = YES;
            self->completion(token, userId, self.email ?: @"");
        }
    }];
}
- (void)cookiesDidChangeInCookieStore:(WKHTTPCookieStore*)store { [self checkCookies]; }
- (void)webView:(WKWebView*)view decidePolicyForNavigationAction:(WKNavigationAction*)action decisionHandler:(void (^)(WKNavigationActionPolicy))handler {
    NSURL* url = action.request.URL;
    if([url.scheme isEqualToString:@"https"] && [url.host isEqualToString:@"accounts.google.com"] && [url.fragment isEqualToString:@"close"]) {
        self.finishRequested = YES;
        [self checkCookies];
    }
    handler(WKNavigationActionPolicyAllow);
}
- (void)webView:(WKWebView*)view didFinishNavigation:(WKNavigation*)navigation {
    NSURL* url = view.URL;
    if([url.scheme isEqualToString:@"https"] && [url.host isEqualToString:@"accounts.google.com"] && [url.fragment isEqualToString:@"close"]) self.finishRequested = YES;
    [self checkCookies];
}
- (void)userContentController:(WKUserContentController*)controller didReceiveScriptMessage:(WKScriptMessage*)message {
    WKSecurityOrigin* origin = message.frameInfo.securityOrigin;
    if(![origin.protocol isEqualToString:@"https"] || ![origin.host isEqualToString:@"accounts.google.com"]) return;
    if([message.name isEqualToString:@"account"] && [message.body isKindOfClass:[NSString class]]) self.email = (NSString*)message.body;
    if([message.name isEqualToString:@"close"]) {
        self.finishRequested = YES;
        [self checkCookies];
    }
}
- (void)webView:(WKWebView*)view didFailProvisionalNavigation:(WKNavigation*)navigation withError:(NSError*)error {
    if(error.code != NSURLErrorCancelled && self->failure) self->failure(error.localizedDescription);
}
@end

const char* const GoogleLoginWindow::DEFAULT_URL = "https://accounts.google.com/embedded/setup/v2/android?source=com.android.settings&xoauth_display_name=MacCraft&canFrp=1&canSk=1&lang=en&langCountry=en_us&hl=en-US&cc=us";

GoogleLoginWindow::GoogleLoginWindow(QWidget* parent) : QDialog(parent) {
    setWindowTitle("MacCraft — Google Sign-In");
    resize(520, 740);
    auto layout = new QVBoxLayout(this);
    auto heading = new QLabel(tr("Sign in with the Google account that owns Minecraft for Android."), this);
    heading->setWordWrap(true);
    layout->addWidget(heading);
    auto host = new QLabel("accounts.google.com", this);
    host->setStyleSheet("color: #528466");
    layout->addWidget(host);
    auto container = new QWidget(this);
    layout->addWidget(container, 1);
    auto status = new QLabel(this);
    status->setWordWrap(true);
    status->hide();
    layout->addWidget(status);
    auto cancel = new QPushButton(tr("Cancel"), this);
    connect(cancel, &QPushButton::clicked, this, &QDialog::reject);
    layout->addWidget(cancel);
    auto configuration = [[WKWebViewConfiguration alloc] init];
    configuration.websiteDataStore = [WKWebsiteDataStore nonPersistentDataStore];
    auto bridge = [[MacCraftGoogleBrowser alloc] init];
    auto controller = [[WKUserContentController alloc] init];
    [controller addScriptMessageHandler:bridge name:@"account"];
    [controller addScriptMessageHandler:bridge name:@"close"];
    NSString* script = @"window.mm={showView:function(){},setAccountIdentifier:function(x){window.webkit.messageHandlers.account.postMessage(String(x));},log:function(){}};window.close=function(){window.webkit.messageHandlers.close.postMessage('close');};";
    [controller addUserScript:[[WKUserScript alloc] initWithSource:script injectionTime:WKUserScriptInjectionTimeAtDocumentStart forMainFrameOnly:YES]];
    configuration.userContentController = controller;
    auto view = [[WKWebView alloc] initWithFrame:NSZeroRect configuration:configuration];
    bridge.webView = view;
    view.navigationDelegate = bridge;
    bridge->completion = [this](NSString* token, NSString* userId, NSString* email) {
        pAccountToken = QString::fromUtf8(token.UTF8String);
        pAccountUserId = QString::fromUtf8(userId.UTF8String);
        pAccountIdentifier = QString::fromUtf8(email.UTF8String);
        accept();
    };
    bridge->failure = [status](NSString* error) {
        status->setText(QString::fromUtf8(error.UTF8String));
        status->show();
    };
    NSView* native = (__bridge NSView*)(reinterpret_cast<void*>(container->winId()));
    view.frame = native.bounds;
    view.autoresizingMask = NSViewWidthSizable | NSViewHeightSizable;
    [native addSubview:view];
    [configuration.websiteDataStore.httpCookieStore addObserver:bridge];
    connect(this, &QObject::destroyed, [view, bridge, controller]() {
        bridge->completion = {};
        bridge->failure = {};
        [view stopLoading];
        view.navigationDelegate = nil;
        [view.configuration.websiteDataStore.httpCookieStore removeObserver:bridge];
        [controller removeScriptMessageHandlerForName:@"account"];
        [controller removeScriptMessageHandlerForName:@"close"];
        [view removeFromSuperview];
    });
    [view loadRequest:[NSURLRequest requestWithURL:[NSURL URLWithString:[NSString stringWithUTF8String:DEFAULT_URL]]]];
}

void GoogleLoginWindow::showWebBrowser() {}
