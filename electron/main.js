

const { app, BrowserWindow } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');
const fs = require('fs');
const pathUp = require('path');

let flaskProcess;

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
  // Lancer le serveur Flask
  console.log("Starting Flask server...");
  console.log(`Current working directory: ${__dirname}`);
  // Trouve le dossier racine du projet (là où se trouve app.py)
  let projectRoot = __dirname;
  while (!fs.existsSync(pathUp.join(projectRoot, 'app.py')) && projectRoot !== pathUp.dirname(projectRoot)) {
    projectRoot = pathUp.dirname(projectRoot);
  }
  console.log(`Project root detected: ${projectRoot}`);
  
  // Utilise le Python de l'environnement virtuel si présent
  let pythonCmd = 'python';
  const isWin = process.platform === 'win32';
  const venvPython = isWin
    ? path.join(projectRoot, '.venv', 'Scripts', 'python.exe')
    : path.join(projectRoot, '.venv', 'bin', 'python');
  if (fs.existsSync(venvPython)) {
    pythonCmd = venvPython;
    console.log('Using virtualenv python:', pythonCmd);
  } else {
    console.log('Using system python:', pythonCmd);
  }
  flaskProcess = spawn(pythonCmd, ['-u', 'app.py'], {
    cwd: projectRoot,
    shell: true,
    env: { ...process.env, PYTHONUNBUFFERED: '1' }
  });

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
