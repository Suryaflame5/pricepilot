const path = require('path');

module.exports = {
  backendUrl: 'http://localhost:8000',
  backendCheckInterval: 1000, // ms
  backendCheckMaxAttempts: 30,
  development: process.env.NODE_ENV === 'development'
};