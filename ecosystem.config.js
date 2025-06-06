module.exports = {
  apps: [{
    name: 'crypto-app',
    script: '/var/www/meusite/app.py',
    interpreter: 'python3',
    cwd: '/var/www/meusite',
    instances: 1,
    exec_mode: 'fork',
    env: {
      FLASK_ENV: 'production',
      PYTHONPATH: '/var/www/meusite',
      PYTHONUNBUFFERED: '1',
      PORT: '8000'  // Adicione esta linha
    },
    log_file: '/var/www/meusite/logs/app.log',
    error_file: '/var/www/meusite/logs/error.log',
    out_file: '/var/www/meusite/logs/out.log',
    log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
    max_restarts: 10,
    restart_delay: 5000,
    min_uptime: '10s',
    watch: false,
    max_memory_restart: '500M',
    kill_timeout: 5000,
    wait_ready: true,
    listen_timeout: 10000
    // Remova esta linha: env_file: '/var/www/meusite/.env'
  }]
}