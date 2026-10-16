#include "MacCraftKeychain.h"
#import <Foundation/Foundation.h>
#import <Security/Security.h>
#include <stdexcept>

static NSMutableDictionary* query() {
    return [@{(__bridge id)kSecClass: (__bridge id)kSecClassGenericPassword,
              (__bridge id)kSecAttrService: @"org.maccraft.launcher.google-play",
              (__bridge id)kSecAttrAccount: @"account-encryption-key"} mutableCopy];
}

QString macCraftReadAccountKey() {
    @autoreleasepool {
        auto request = query();
        request[(__bridge id)kSecReturnData] = @YES;
        request[(__bridge id)kSecMatchLimit] = (__bridge id)kSecMatchLimitOne;
        CFTypeRef result = nullptr;
        const auto status = SecItemCopyMatching((__bridge CFDictionaryRef)request, &result);
        if(status == errSecItemNotFound) return {};
        if(status != errSecSuccess)
            throw std::runtime_error("MacCraft could not read its login keychain. Unlock your macOS login keychain and try again.");
        NSData* data = CFBridgingRelease(result);
        return QString::fromUtf8(static_cast<const char*>(data.bytes), static_cast<qsizetype>(data.length));
    }
}

void macCraftStoreAccountKey(const QString& key) {
    @autoreleasepool {
        const auto bytes = key.toUtf8();
        NSData* value = [NSData dataWithBytes:bytes.constData() length:bytes.size()];
        auto request = query();
        auto status = SecItemUpdate((__bridge CFDictionaryRef)request,
            (__bridge CFDictionaryRef)@{(__bridge id)kSecValueData: value});
        if(status == errSecItemNotFound) {
            request[(__bridge id)kSecValueData] = value;
            request[(__bridge id)kSecAttrAccessible] = (__bridge id)kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly;
            status = SecItemAdd((__bridge CFDictionaryRef)request, nullptr);
        }
        if(status != errSecSuccess)
            throw std::runtime_error("MacCraft could not save its login to the macOS keychain. No account has been saved. Unlock your login keychain and try again.");
    }
}

void macCraftDeleteAccountKey() {
    @autoreleasepool {
        const auto status = SecItemDelete((__bridge CFDictionaryRef)query());
        if(status != errSecSuccess && status != errSecItemNotFound)
            throw std::runtime_error("MacCraft could not remove its login key from the macOS keychain.");
    }
}
