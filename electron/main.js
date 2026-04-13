

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

  flaskProcess.stdout.on('data', (data) => {
    console.log(`[Flask] ${data}`);
  });
  flaskProcess.stderr.on('data', (data) => {
    console.error(`[Flask ERROR] ${data}`);
  });
  flaskProcess.on('exit', (code, signal) => {
    console.error(`[Flask] Process exited with code ${code}, signal ${signal}`);
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
    app.quit();
  });

  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

function killFlask() {
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
