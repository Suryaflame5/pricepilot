const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');
const net = require('net');

let mainWindow;
let backendProcess;
let backendPort = 8000;

// Find available port
function findAvailablePort(startPort) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.listen(startPort, () => {
      const port = server.address().port;
      server.close(() => resolve(port));
    });
    server.on('error', () => {
      resolve(findAvailablePort(startPort + 1));
    });
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    },
    icon: path.join(__dirname, '../public/icon.png')
  });

  // Load the Next.js app
  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:3000');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../.next/standalone/index.html'));
  }
}

function startBackend(port) {
  const pythonPath = path.join(process.resourcesPath, 'backend', 'api.exe');
  const backendDir = path.join(process.resourcesPath, 'backend');
  
  console.log('Starting backend from:', pythonPath);
  console.log('Backend port:', port);
  
  backendProcess = spawn(pythonPath, [], {
    cwd: backendDir,
    stdio: 'inherit',
    env: { ...process.env, API_PORT: port.toString() }
  });

  backendProcess.on('error', (error) => {
    console.error('Failed to start backend:', error);
  });

  backendProcess.on('close', (code) => {
    console.log(`Backend process exited with code ${code}`);
  });
}

function checkBackendReady(port, callback) {
  const maxAttempts = 30;
  let attempts = 0;

  const check = () => {
    http.get(`http://localhost:${port}/health`, (res) => {
      if (res.statusCode === 200) {
        callback(true);
      } else {
        retry();
      }
    }).on('error', retry);
  };

  const retry = () => {
    attempts++;
    if (attempts < maxAttempts) {
      setTimeout(check, 1000);
    } else {
      callback(false);
    }
  };

  check();
}

app.whenReady().then(async () => {
  // Find available port and start backend
  if (process.env.NODE_ENV !== 'development') {
    backendPort = await findAvailablePort(8000);
    startBackend(backendPort);
    
    // Wait for backend to be ready before showing window
    checkBackendReady(backendPort, (ready) => {
      if (ready) {
        console.log('Backend is ready on port:', backendPort);
        createWindow();
      } else {
        console.error('Backend failed to start');
        app.quit();
      }
    });
  } else {
    createWindow();
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  if (backendProcess) {
    backendProcess.kill();
  }
});

// IPC handlers for communication with renderer
ipcMain.handle('get-backend-url', () => {
  return `http://localhost:${backendPort}`;
});

ipcMain.handle('get-app-version', () => {
  return app.getVersion();
});