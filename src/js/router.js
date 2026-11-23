/**
 * Navegación por hash: #/tablero, #/consulta, #/ficha/<id>.
 * Cada ruta es una vista con render(container, params).
 */
const DEFAULT_ROUTE = 'tablero';

export function parse(hash = location.hash) {
  const [name, ...rest] = hash.replace(/^#\/?/, '').split('/');
  return { name: name || DEFAULT_ROUTE, param: rest.length ? decodeURIComponent(rest.join('/')) : null };
}

export function href(name, param) {
  return `#/${name}${param ? '/' + encodeURIComponent(param) : ''}`;
}

export function start(routes, onRoute) {
  const go = () => {
    const route = parse();
    const view = routes[route.name] ? route.name : DEFAULT_ROUTE;
    onRoute(view, routes[view], route.param);
  };
  window.addEventListener('hashchange', go);
  go();
}
