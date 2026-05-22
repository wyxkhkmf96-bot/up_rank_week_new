// 静态文件服务（端口 8082）- 充电UP主分析看板
// 用法: node static-server.js
const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = 8082;
const DIR = __dirname;
const MIME = {
    '.html': 'text/html; charset=utf-8',
    '.js':   'text/javascript; charset=utf-8',
    '.css':  'text/css; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.csv':  'text/csv; charset=utf-8',
    '.png':  'image/png',
    '.svg':  'image/svg+xml',
    '.jpg':  'image/jpeg',
    '.jpeg': 'image/jpeg'
};

http.createServer((req, res) => {
    const urlPath = (req.url === '/' ? '/charging_up_leaderboard.html' : req.url.split('?')[0]);
    const fp = path.join(DIR, decodeURIComponent(urlPath));
    const isInside = fp.startsWith(DIR);
    if (!isInside) {
        res.writeHead(403);
        res.end('Forbidden');
        return;
    }
    if (fs.existsSync(fp) && fs.statSync(fp).isFile()) {
        const ext = path.extname(fp).toLowerCase();
        res.setHeader('Content-Type', MIME[ext] || 'application/octet-stream');
        res.setHeader('Cache-Control', 'no-cache');
        fs.createReadStream(fp).pipe(res);
    } else {
        res.writeHead(404);
        res.end('Not found');
    }
}).listen(PORT, '0.0.0.0', () => {
    console.log('HTTP server on http://0.0.0.0:' + PORT);
    console.log('Serving dir: ' + DIR);
});
