// Serves site/ under https://theaipipe.com/demos/one-script-video-flow/ (static files only).
// The route is more specific than the galerie-presell route theaipipe.com/demos/*, so it wins.
// Byte ranges are answered here so the browser can seek inside the videos ("See source scene").
const BASE = '/demos/one-script-video-flow';
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === BASE) return Response.redirect(`${url.origin}${BASE}/`, 308);
    if (/\/\/+/.test(url.pathname)) {
      return Response.redirect(`${url.origin}${url.pathname.replace(/\/\/+/g, '/')}${url.search}`, 308);
    }
    if (!url.pathname.startsWith(BASE + '/')) return new Response('Not found', { status: 404 });
    const path = url.pathname.slice(BASE.length) || '/';
    const res = await env.ASSETS.fetch(new Request(new URL(path, url.origin), { method: 'GET' }));
    const range = request.headers.get('Range');
    const m = range && /^bytes=(\d*)-(\d*)$/.exec(range.trim());
    let out;
    if (res.status === 200 && m && /\.mp4$/.test(path)) {
      const buf = await res.arrayBuffer();
      const size = buf.byteLength;
      let start = m[1] === '' ? size - Number(m[2]) : Number(m[1]);
      let end = m[1] !== '' && m[2] !== '' ? Math.min(Number(m[2]), size - 1) : size - 1;
      if (start < 0) start = 0;
      if (start >= size || start > end) {
        return new Response(null, { status: 416, headers: { 'Content-Range': `bytes */${size}` } });
      }
      const h = new Headers(res.headers);
      h.set('Content-Range', `bytes ${start}-${end}/${size}`);
      h.set('Content-Length', String(end - start + 1));
      h.set('Accept-Ranges', 'bytes');
      out = new Response(request.method === 'HEAD' ? null : buf.slice(start, end + 1), { status: 206, headers: h });
    } else {
      out = new Response(request.method === 'HEAD' ? null : res.body, res);
      if (/\.mp4$/.test(path)) out.headers.set('Accept-Ranges', 'bytes');
    }
    const loc = out.headers.get('Location');
    if (loc && loc.startsWith('/')) out.headers.set('Location', BASE + loc);
    out.headers.set('X-Robots-Tag', 'noindex, nofollow');
    return out;
  },
};
