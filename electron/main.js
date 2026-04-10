

const { app, BrowserWindow } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');
const fs = require('fs');

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
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true
    }
  });
  win.setMenuBarVisibility(false);
  win.webContents.session.clearCache();
  win.loadURL('http://127.0.0.1:8080');
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
    createWindow();
  }).catch((err) => {
    console.error('Le serveur Flask n\'a pas démarré à temps:', err);
    app.quit();
  });

  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', function () {
  if (process.platform !== 'darwin') {
    app.quit();
  }
  if (flaskProcess) {
    flaskProcess.kill();
  }
});
