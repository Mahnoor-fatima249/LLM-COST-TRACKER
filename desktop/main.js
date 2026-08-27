const { app, BrowserWindow, shell, dialog, Menu, Tray, nativeImage, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');

let mainWindow = null;
let splashWindow = null;
let serverProcess = null;
let tray = null;
const SERVER_PORT = 18923;
const SERVER_URL = `http://127.0.0.1:${SERVER_PORT}`;
const APP_VERSION = '2.0.0';

function findPython() {
  return 'python';
}

function startServer() {
  return new Promise((resolve, reject) => {
    const python = findPython();
    const appDir = path.join(__dirname, '..');

    serverProcess = spawn(python, [
      '-m', 'uvicorn', 'app.main:app',
      '--host', '127.0.0.1',
      '--port', String(SERVER_PORT),
    ], {
      cwd: appDir,
      stdio: ['ignore', 'pipe', 'pipe'],
      env: { ...process.env, PYTHONUNBUFFERED: '1' },
    });

    let resolved = false;

    serverProcess.stdout.on('data', (data) => {
      if (data.toString().includes('Application startup complete') && !resolved) {
        resolved = true;
        resolve();
      }
    });

    serverProcess.stderr.on('data', (data) => {
      if (data.toString().includes('Application startup complete') && !resolved) {
        resolved = true;
        resolve();
      }
    });

    serverProcess.on('error', (err) => {
      if (!resolved) { resolved = true; reject(err); }
    });

    serverProcess.on('exit', (code) => {
      if (code && code !== 0 && code !== null && !resolved) {
        resolved = true;
        reject(new Error(`Server exited with code ${code}`));
      }
    });

    setTimeout(() => { if (!resolved) { resolved = true; resolve(); } }, 10000);
  });
}

function waitForServer(retries = 40) {
  return new Promise((resolve, reject) => {
    let attempts = 0;
    const check = () => {
      http.get(`${SERVER_URL}/api/health`, (res) => {
        if (res.statusCode === 200) resolve();
        else retry();
      }).on('error', () => retry());
    };
    const retry = () => {
      attempts++;
      if (attempts >= retries) reject(new Error('Server did not start'));
      else setTimeout(check, 500);
    };
    check();
  });
}

function createSplash() {
  splashWindow = new BrowserWindow({
    width: 480,
    height: 340,
    frame: false,
    transparent: true,
    resizable: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    webPreferences: { nodeIntegration: false, contextIsolation: true },
  });

  splashWindow.loadURL(`data:text/html,<!DOCTYPE html>
<html><head><style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{background:transparent;display:flex;align-items:center;justify-content:center;height:100vh;font-family:'Inter',system-ui,sans-serif}
  .splash{width:440px;height:300px;background:linear-gradient(145deg,#0e0e1a 0%,#151530 50%,#0e0e1a 100%);border-radius:24px;border:1px solid rgba(255,255,255,0.06);display:flex;flex-direction:column;align-items:center;justify-content:center;position:relative;overflow:hidden;box-shadow:0 25px 80px rgba(0,0,0,0.6)}
  .splash::before{content:'';position:absolute;top:-60px;right:-60px;width:200px;height:200px;background:radial-gradient(circle,rgba(99,102,241,0.15),transparent 70%);border-radius:50%}
  .splash::after{content:'';position:absolute;bottom:-40px;left:-40px;width:160px;height:160px;background:radial-gradient(circle,rgba(6,182,212,0.12),transparent 70%);border-radius:50%}
  .logo{width:64px;height:64px;margin-bottom:20px;position:relative;z-index:1}
  .logo svg{width:100%;height:100%}
  .title{font-size:22px;font-weight:800;letter-spacing:-0.5px;color:#e2e8f0;position:relative;z-index:1;margin-bottom:4px}
  .subtitle{font-size:12px;color:#64748b;letter-spacing:2px;text-transform:uppercase;position:relative;z-index:1;margin-bottom:32px}
  .loader-wrap{position:relative;z-index:1;width:200px}
  .loader-bar{height:3px;background:rgba(255,255,255,0.06);border-radius:99px;overflow:hidden}
  .loader-fill{height:100%;width:0%;background:linear-gradient(90deg,#6366f1,#06b6d4);border-radius:99px;animation:load 2.5s ease-in-out forwards}
  .loader-text{font-size:11px;color:#475569;margin-top:12px;text-align:center;animation:pulse 1.5s ease infinite}
  @keyframes load{0%{width:0%}30%{width:45%}60%{width:70%}90%{width:90%}100%{width:100%}}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:0.5}}
</style></head><body>
  <div class="splash">
    <div class="logo">
      <svg viewBox="0 0 64 64" fill="none"><rect width="64" height="64" rx="18" fill="url(#sg)"/><path d="M18 32C18 24.27 24.27 18 32 18C39.73 18 46 24.27 46 32" stroke="white" stroke-width="3.5" stroke-linecap="round"/><path d="M25 32C25 28.13 28.13 25 32 25C35.87 25 39 28.13 39 32" stroke="white" stroke-width="3.5" stroke-linecap="round"/><circle cx="32" cy="32" r="3.5" fill="white"/><path d="M32 35.5V46" stroke="white" stroke-width="3.5" stroke-linecap="round"/><path d="M27 42H37" stroke="white" stroke-width="3.5" stroke-linecap="round"/><defs><linearGradient id="sg" x1="0" y1="0" x2="64" y2="64"><stop stop-color="#6366f1"/><stop offset="1" stop-color="#06b6d4"/></linearGradient></defs></svg>
    </div>
    <div class="title">LLM Cost Tracker</div>
    <div class="subtitle">Smart AI Spend Management</div>
    <div class="loader-wrap">
      <div class="loader-bar"><div class="loader-fill"></div></div>
      <div class="loader-text">Starting server...</div>
    </div>
  </div>
</body></html>`);
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 960,
    minHeight: 640,
    frame: false,
    titleBarStyle: 'hidden',
    backgroundColor: '#08080d',
    show: false,
    icon: path.join(__dirname, 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  mainWindow.on('closed', () => { mainWindow = null; });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  ipcMain.on('window-minimize', () => mainWindow?.minimize());
  ipcMain.on('window-maximize', () => {
    if (mainWindow?.isMaximized()) mainWindow.unmaximize();
    else mainWindow?.maximize();
  });
  ipcMain.on('window-close', () => mainWindow?.close());

  mainWindow.on('maximize', () => {
    mainWindow?.webContents.send('window-maximized', true);
  });
  mainWindow.on('unmaximize', () => {
    mainWindow?.webContents.send('window-maximized', false);
  });
}

function createMenu() {
  const template = [
    {
      label: 'File',
      submenu: [
        { label: 'Export Data', accelerator: 'CmdOrCtrl+E', click: () => mainWindow?.webContents.executeJavaScript('exportCSV()') },
        { type: 'separator' },
        { role: 'quit' },
      ],
    },
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' }, { role: 'redo' }, { type: 'separator' },
        { role: 'cut' }, { role: 'copy' }, { role: 'paste' }, { role: 'selectAll' },
      ],
    },
    {
      label: 'View',
      submenu: [
        { role: 'reload', accelerator: 'CmdOrCtrl+R' },
        { role: 'forceReload', accelerator: 'CmdOrCtrl+Shift+R' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'resetZoom' }, { role: 'zoomIn' }, { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' },
      ],
    },
    {
      label: 'Window',
      submenu: [
        { role: 'minimize' },
        { role: 'maximize' },
        { role: 'close' },
      ],
    },
    {
      label: 'Help',
      submenu: [
        {
          label: `About LLM Cost Tracker`,
          click: () => {
            dialog.showMessageBox(mainWindow, {
              type: 'info',
              title: 'About LLM Cost Tracker',
              message: 'LLM Cost Tracker',
              detail: `Version: ${APP_VERSION}\nReal-time AI API cost monitoring.\n\nTrack, analyze, and optimize your LLM spending across all providers.`,
            });
          },
        },
        { type: 'separator' },
        {
          label: 'Learn More',
          click: () => shell.openExternal('https://github.com/yourusername/llm-cost-tracker'),
        },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

function createTray() {
  const icon = nativeImage.createEmpty();
  tray = new Tray(icon);
  tray.setToolTip('LLM Cost Tracker');
  tray.on('click', () => {
    if (mainWindow) {
      mainWindow.isVisible() ? mainWindow.focus() : mainWindow.show();
    }
  });
}

app.whenReady().then(async () => {
  createSplash();
  createMainWindow();
  createMenu();
  createTray();

  try {
    await startServer();
    await waitForServer();

    if (splashWindow) {
      splashWindow.close();
      splashWindow = null;
    }

    if (mainWindow) {
      mainWindow.loadURL(SERVER_URL);
      mainWindow.once('ready-to-show', () => mainWindow.show());
    }
  } catch (err) {
    if (splashWindow) splashWindow.close();
    dialog.showErrorBox('Startup Error', `Failed to start:\n${err.message}`);
    app.quit();
  }
});

app.on('window-all-closed', () => {
  if (serverProcess) serverProcess.kill('SIGTERM');
  app.quit();
});

app.on('before-quit', () => {
  if (serverProcess) serverProcess.kill('SIGTERM');
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createMainWindow();
});
