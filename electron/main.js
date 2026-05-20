

const { app, BrowserWindow, dialog } = require('electron');
const { spawn, execSync } = require('child_process');
const path = require('path');
const http = require('http');
const fs = require('fs');
const { autoUpdater } = require('electron-updater');

let flaskProcess;

function isPackaged() {
  return app.isPackaged;
}

function getResourcePath(...parts) {
  if (isPackaged()) {
    return path.join(process.resourcesPath, ...parts);
  }
  // Dev mode: project root is one level up from electron/
  const projectRoot = path.resolve(__dirname, '..');
  return path.join(projectRoot, ...parts);
}

function waitForServer(url, timeout = 120000) {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    function check() {
      http.get(url, res => {
        resolve();
      }).on('error', err => {
        if (Date.now() - start > timeout) {
          reject(new Error('Timeout waiting for server'));
        } else {
          setTimeout(check, 1000);
        }
      });
    }
    check();
  });
}

function createWindow () {
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    autoHideMenuBar: true,
    icon: path.join(__dirname, 'icon.png'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true
    }
  });
  win.setMenuBarVisibility(false);
  win.loadURL('http://127.0.0.1:8080');

  // Open target="_blank" links (e.g. guide) in a new frameless-menu window
  win.webContents.setWindowOpenHandler(({ url }) => {
    const child = new BrowserWindow({
      width: 1000,
      height: 800,
      autoHideMenuBar: true,
      icon: path.join(__dirname, 'icon.png'),
      webPreferences: {
        nodeIntegration: false,
        contextIsolation: true
      }
    });
    child.setMenuBarVisibility(false);
    child.loadURL(url);
    return { action: 'deny' };
  });

  return win;
}

// --- Auto-update ---
function setupAutoUpdater() {
  if (!isPackaged()) {
    console.log('[Updater] Skipping auto-update in dev mode');
    return;
  }

  autoUpdater.autoDownload = true;
  autoUpdater.autoInstallOnAppQuit = true;
  autoUpdater.logger = console;

  autoUpdater.on('checking-for-update', () => {
    console.log('[Updater] Checking for updates...');
  });

  autoUpdater.on('update-available', (info) => {
    console.log(`[Updater] Update available: ${info.version}`);
  });

  autoUpdater.on('update-not-available', () => {
    console.log('[Updater] App is up to date');
  });

  autoUpdater.on('download-progress', (progress) => {
    console.log(`[Updater] Download: ${Math.round(progress.percent)}%`);
  });

  autoUpdater.on('update-downloaded', (info) => {
    console.log(`[Updater] Update downloaded: ${info.version}`);
    const win = BrowserWindow.getFocusedWindow();
    dialog.showMessageBox(win, {
      type: 'info',
      title: 'Mise à jour disponible',
      message: `La version ${info.version} a été téléchargée.\nL'application va redémarrer pour appliquer la mise à jour.`,
      buttons: ['Redémarrer maintenant', 'Plus tard'],
      defaultId: 0,
    }).then((result) => {
      if (result.response === 0) {
        autoUpdater.quitAndInstall(false, true);
      }
    });
  });

  autoUpdater.on('error', (err) => {
    console.error('[Updater] Error:', err.message);
  });

  // Check for updates after a short delay
  setTimeout(() => {
    autoUpdater.checkForUpdates().catch(err => {
      console.error('[Updater] Check failed:', err.message);
    });
  }, 5000);
}

app.whenReady().then(() => {
  console.log("Starting Flask server...");
  console.log(`Packaged: ${isPackaged()}`);

  // --- Backend logging to a file for debugging ---
  // macOS:   ~/Library/Logs/NutriProof/backend.log
  // Windows: %APPDATA%\NutriProof\logs\backend.log
  // Linux:   ~/.config/NutriProof/logs/backend.log
  const logsDir = app.getPath('logs');
  try { fs.mkdirSync(logsDir, { recursive: true }); } catch (e) { /* ignore */ }
  const backendLogPath = path.join(logsDir, 'backend.log');
  let backendLog;
  try {
    // Truncate at every launch so the log reflects the current session.
    backendLog = fs.createWriteStream(backendLogPath, { flags: 'w' });
    backendLog.write(`=== NutriProof backend log ===\n`);
    backendLog.write(`Started: ${new Date().toISOString()}\n`);
    backendLog.write(`App version: ${app.getVersion()}\n`);
    backendLog.write(`Platform: ${process.platform} ${process.arch}\n`);
    backendLog.write(`Electron: ${process.versions.electron}\n`);
    backendLog.write(`Log file: ${backendLogPath}\n\n`);
    console.log(`[Backend log] ${backendLogPath}`);
  } catch (e) {
    console.error('Failed to open backend log file:', e);
  }
  function logBackend(prefix, chunk) {
    const text = chunk.toString();
    if (backendLog) {
      try { backendLog.write(`[${prefix}] ${text}`); } catch (e) { /* ignore */ }
    }
  }

  let backendExe, backendCwd, envVars;

  if (isPackaged()) {
    // Packaged mode: use PyInstaller-bundled backend
    const exeName = process.platform === 'win32' ? 'app.exe' : 'app';
    backendExe = getResourcePath('backend', exeName);
    backendCwd = getResourcePath('backend');
    const tesseractDir = getResourcePath('tesseract-bundle');
    const tesseractBin = process.platform === 'win32'
      ? tesseractDir
      : path.join(tesseractDir, 'bin');
    // Windows: tessdata is at tesseract-bundle/tessdata
    // macOS:   tessdata is at tesseract-bundle/share/tessdata
    const tessDataDir = process.platform === 'win32'
      ? path.join(tesseractDir, 'tessdata')
      : path.join(tesseractDir, 'share', 'tessdata');
    envVars = {
      ...process.env,
      PYTHONUNBUFFERED: '1',
      TESSERACT_PATH: tesseractBin,
      TESSDATA_PREFIX: tessDataDir
    };
    // macOS: ensure the bundled tesseract can find its dylibs even if rpath
    // resolution fails (defense-in-depth — needs allow-dyld-environment-variables entitlement).
    if (process.platform === 'darwin') {
      const tessLib = path.join(tesseractDir, 'lib');
      envVars.DYLD_FALLBACK_LIBRARY_PATH = tessLib +
        (process.env.DYLD_FALLBACK_LIBRARY_PATH ? ':' + process.env.DYLD_FALLBACK_LIBRARY_PATH : '');
    }
    console.log(`Backend exe: ${backendExe}`);
    console.log(`Tesseract bin: ${tesseractBin}`);
    console.log(`Tessdata: ${tessDataDir}`);

    flaskProcess = spawn(backendExe, [], {
      cwd: backendCwd,
      env: envVars
    });
  } else {
    // Dev mode: run Python directly
    let projectRoot = __dirname;
    while (!fs.existsSync(path.join(projectRoot, 'app.py')) && projectRoot !== path.dirname(projectRoot)) {
      projectRoot = path.dirname(projectRoot);
    }
    console.log(`Project root: ${projectRoot}`);

    let pythonCmd = 'python';
    const venvPython = process.platform === 'win32'
      ? path.join(projectRoot, '.venv', 'Scripts', 'python.exe')
      : path.join(projectRoot, '.venv', 'bin', 'python');
    if (fs.existsSync(venvPython)) {
      pythonCmd = venvPython;
      console.log('Using venv python:', pythonCmd);
    }

    flaskProcess = spawn(pythonCmd, ['-u', 'app.py'], {
      cwd: projectRoot,
      shell: true,
      env: { ...process.env, PYTHONUNBUFFERED: '1' }
    });
  }

  if (backendLog) {
    backendLog.write(`Backend exe: ${backendExe || '(python dev mode)'}\n`);
    backendLog.write(`Backend cwd: ${backendCwd || '(project root)'}\n`);
    backendLog.write(`Env TESSERACT_PATH: ${envVars && envVars.TESSERACT_PATH || ''}\n`);
    backendLog.write(`Env TESSDATA_PREFIX: ${envVars && envVars.TESSDATA_PREFIX || ''}\n`);
    backendLog.write(`Env DYLD_FALLBACK_LIBRARY_PATH: ${envVars && envVars.DYLD_FALLBACK_LIBRARY_PATH || ''}\n\n`);
  }

  flaskProcess.stdout.on('data', (data) => {
    console.log(`[Flask] ${data}`);
    logBackend('stdout', data);
  });
  flaskProcess.stderr.on('data', (data) => {
    console.error(`[Flask ERROR] ${data}`);
    logBackend('stderr', data);
  });
  flaskProcess.on('error', (err) => {
    console.error(`[Flask] Failed to start process:`, err);
    if (backendLog) backendLog.write(`\n[spawn-error] ${err.stack || err.message}\n`);
    dialog.showErrorBox('Erreur de démarrage',
      `Impossible de lancer le serveur backend.\n\n${err.message}\n\nChemin: ${backendExe || 'python'}\n\nLog: ${backendLogPath}`);
    app.quit();
  });
  flaskProcess.on('exit', (code, signal) => {
    console.error(`[Flask] Process exited with code ${code}, signal ${signal}`);
    if (backendLog) {
      backendLog.write(`\n[exit] code=${code} signal=${signal} at ${new Date().toISOString()}\n`);
      try { backendLog.end(); } catch (e) { /* ignore */ }
    }
    if (code !== 0 && code !== null && !isQuittingApp) {
      dialog.showErrorBox('Erreur backend',
        `Le serveur backend s'est arrêté de manière inattendue.\n\nCode: ${code}\nSignal: ${signal}\n\nLog: ${backendLogPath}`);
    }
  });

  // Attendre que le serveur Flask soit prêt
  waitForServer('http://127.0.0.1:8080').then(() => {
    const win = createWindow();

    // Sign out Firebase when window is closed without logout button
    let isQuitting = false;
    win.on('close', (e) => {
      if (isQuitting) return;
      isQuitting = true;
      e.preventDefault();
      win.webContents.executeJavaScript(
        'firebase && firebase.auth ? firebase.auth().signOut().catch(()=>{}) : Promise.resolve()'
      ).finally(() => {
        win.destroy();
      });
    });

    setupAutoUpdater();
  }).catch((err) => {
    console.error('Le serveur Flask n\'a pas démarré à temps:', err);
    dialog.showErrorBox('Délai d\'attente dépassé',
      'Le serveur backend n\'a pas répondu après 2 minutes.\n\nVérifiez qu\'aucun autre programme n\'utilise le port 8080.');
    app.quit();
  });

  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

let isQuittingApp = false;

function killFlask() {
  isQuittingApp = true;
  if (flaskProcess) {
    try {
      if (process.platform === 'win32') {
        execSync(`taskkill /pid ${flaskProcess.pid} /T /F`, { stdio: 'ignore' });
      } else {
        flaskProcess.kill('SIGTERM');
      }
    } catch (e) {
      // Process may already be dead
    }
    flaskProcess = null;
  }
}

app.on('before-quit', () => {
  killFlask();
});

app.on('window-all-closed', function () {
  killFlask();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
