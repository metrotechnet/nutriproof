/* eslint-disable */
// electron-builder afterSign hook
// Signing is intentionally disabled for local/CI builds.
// The original implementation is kept below as commented reference only.
//
// const { execSync } = require('child_process');
// const fs = require('fs');
// const path = require('path');
//
// function isMachO(filePath) {
//     ...
// }
//
// function walk(dir, out = []) {
//     ...
// }
//
// exports.default = async function afterSign(context) {
//     const { electronPlatformName, appOutDir, packager } = context;
//     if (electronPlatformName !== 'darwin') return;
//
//     const identity = process.env.CSC_NAME || process.env.MAC_SIGN_IDENTITY;
//     let signIdentity = identity;
//     if (!signIdentity) {
//         try {
//             const out = execSync('security find-identity -v -p codesigning', { encoding: 'utf8' });
//             const m = out.match(/"(Developer ID Application:[^"]+)"/);
//             if (m) signIdentity = m[1];
//         } catch (e) {
//             console.warn('[afterSign] could not auto-detect signing identity:', e.message);
//         }
//     }
//     if (!signIdentity) {
//         console.warn('[afterSign] No Developer ID Application identity found; skipping embedded binary signing.');
//         return;
//     }
//
//     const appName = packager.appInfo.productFilename;
//     const appPath = path.join(appOutDir, `${appName}.app`);
//     const entitlements = path.resolve(__dirname, 'entitlements.mac.plist');
//
//     // ... original signing logic remains commented out ...
// };

exports.default = async function afterSign() {
    // No-op: unsigned builds are intentionally used.
    return;
};
