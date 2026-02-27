from http.server import BaseHTTPRequestHandler,HTTPServer; import urllib.parse as u
class H(BaseHTTPRequestHandler):
  def do_GET(s):
    q=u.parse_qs(u.urlparse(s.path).query); print('CODE=', q.get('code',[''])[0]); print('STATE=', q.get('state',[''])[0])
    s.send_response(200); s.send_header('Content-Type','text/plain'); s.end_headers()
    s.wfile.write(b'OK. You can close this tab.')
HTTPServer(('127.0.0.1',8888), H).serve_forever()
