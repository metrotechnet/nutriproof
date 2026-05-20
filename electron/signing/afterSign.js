/* eslint-disable */
// electron-builder afterSign hook
// Signs embedded binaries inside the .app's Resources/ directory that
// electron-builder does NOT sign automatically (Tesseract executable,
// .dylib files, and the PyInstaller backend executable).
//
// Without this, notarization fails because hardened runtime requires
// every Mach-O binary inside the bundle to be signed with the same identity
// and entitlements.

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

function isMachO(filePath) {
    try {
        const fd = fs.openSync(filePath, 'r');
        const buf = Buffer.alloc(4);
        fs.readSync(fd, buf, 0, 4, 0);
        fs.closeSync(fd);
        const magic = buf.readUInt32BE(0);
        // Mach-O magic numbers (big and little endian, 32/64, fat)
        return (
            magic === 0xfeedface ||
            magic === 0xcefaedfe ||
            magic === 0xfeedfacf ||
            magic === 0xcffaedfe ||
            magic === 0xcafebabe ||
            magic === 0xbebafeca
        );
    } catch (e) {
        return false;
    }
}

function walk(dir, out = []) {
    let entries;
    try {
        entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch (e) {
        return out;
    }
    for (const entry of entries) {
        const full = path.join(dir, entry.name);
        if (entry.isSymbolicLink()) continue;
        if (entry.isDirectory()) {
            walk(full, out);
        } else if (entry.isFile()) {
            out.push(full);
        }
    }
    return out;
}

exports.default = async function afterSign(context) {
    const { electronPlatformName, appOutDir, packager } = context;
    if (electronPlatformName !== 'darwin') return;

    const identity = process.env.CSC_NAME || process.env.MAC_SIGN_IDENTITY;
    // electron-builder uses the cert from CSC_LINK; we resolve the identity from `security find-identity`
    let signIdentity = identity;
    if (!signIdentity) {
        try {
            const out = execSync('security find-identity -v -p codesigning', { encoding: 'utf8' });
            const m = out.match(/"(Developer ID Application:[^"]+)"/);
            if (m) signIdentity = m[1];
        } catch (e) {
            console.warn('[afterSign] could not auto-detect signing identity:', e.message);
        }
    }
    if (!signIdentity) {
        console.warn('[afterSign] No Developer ID Application identity found; skipping embedded binary signing.');
        return;
    }

    const appName = packager.appInfo.productFilename;
    const appPath = path.join(appOutDir, `${appName}.app`);
    const entitlements = path.resolve(__dirname, 'entitlements.mac.plist');

    console.log(`[afterSign] Identity: ${signIdentity}`);
    console.log(`[afterSign] Scanning: ${appPath}`);

    // Scan the WHOLE .app, not just Resources/. electron-builder misses certain
    // binaries (e.g. Electron's libEGL.dylib, Squirrel.framework/ShipIt) which
    // causes notarization to fail with "binary is not signed".
    const candidates = walk(appPath).filter((f) => {
        const base = path.basename(f);
        if (base.endsWith('.dylib') || base.endsWith('.so')) return true;
        try {
            const st = fs.statSync(f);
            if ((st.mode & 0o111) !== 0 && !path.extname(f)) return true;
        } catch (e) { /* ignore */ }
        return isMachO(f);
    });

    // Deduplicate via realpath
    const seen = new Set();
    const targets = [];
    for (const c of candidates) {
        try {
            const real = fs.realpathSync(c);
            if (seen.has(real)) continue;
            seen.add(real);
            if (isMachO(real)) targets.push(real);
        } catch (e) { /* ignore */ }
    }

    // Helper: check if a binary is already signed with a secure timestamp + hardened runtime.
    function isProperlySigned(filePath) {
        try {
            const out = execSync(`codesign -dv --verbose=4 "${filePath}" 2>&1`, { encoding: 'utf8' });
            const hasTimestamp = /Timestamp=/.test(out) && !/Signed Time=/.test(out.split('\n').find(l => l.startsWith('Signed Time=')) || '');
            const hasRuntime = /flags=.*runtime/.test(out) || /CodeDirectory.*runtime/.test(out);
            // Consider it OK only if it has both a secure timestamp AND hardened runtime.
            return /Timestamp=/.test(out) && hasRuntime;
        } catch (e) {
            return false;
        }
    }

    console.log(`[afterSign] Found ${targets.length} Mach-O binaries in app bundle.`);
    let signedCount = 0;
    let skippedCount = 0;
    for (const t of targets) {
        if (isProperlySigned(t)) {
            skippedCount++;
            continue;
        }
        try {
            console.log(`[afterSign] signing: ${path.relative(appPath, t)}`);
            execSync(
                `codesign --force --timestamp --options runtime --entitlements "${entitlements}" --sign "${signIdentity}" "${t}"`,
                { stdio: 'inherit' }
            );
            signedCount++;
        } catch (e) {
            console.error(`[afterSign] FAILED to sign ${t}:`, e.message);
            throw e;
        }
    }
    console.log(`[afterSign] Signed ${signedCount} binaries, skipped ${skippedCount} already-signed.`);

    // Re-sign the .app shell so its outer signature covers any newly-signed nested binaries.
    console.log(`[afterSign] Re-signing app bundle: ${appPath}`);
    execSync(
        `codesign --force --timestamp --options runtime --entitlements "${entitlements}" --sign "${signIdentity}" "${appPath}"`,
        { stdio: 'inherit' }
    );

    // Verify the final bundle
    console.log(`[afterSign] Verifying...`);
    execSync(`codesign --verify --deep --strict --verbose=2 "${appPath}"`, { stdio: 'inherit' });

    console.log('[afterSign] Done.');
};
