// Reproduce Qt Cocoa's default application-icon query without Python or Qt.
#import <AppKit/AppKit.h>
#import <UniformTypeIdentifiers/UniformTypeIdentifiers.h>
#include <cstdio>

int main() {
    @autoreleasepool {
        [NSApplication sharedApplication];
        puts("Cocoa initialized; requesting application bundle icon"); fflush(stdout);
        NSImage *generic = [NSWorkspace.sharedWorkspace iconForContentType:UTTypeApplicationBundle];
        puts("Generic icon returned; requesting application icon"); fflush(stdout);
        NSImage *application = [NSImage imageNamed:NSImageNameApplicationIcon];
        NSRect rect = NSMakeRect(0, 0, 32, 32);
        CGImageRef first = [application CGImageForProposedRect:&rect context:nil hints:nil];
        puts("Application CGImage returned; requesting generic CGImage"); fflush(stdout);
        CGImageRef second = [generic CGImageForProposedRect:&rect context:nil hints:nil];
        if (!first || !second) return 2;
        puts("Native Cocoa IconServices PASS; no Qt/runtime qualification claimed");
    }
    return 0;
}
