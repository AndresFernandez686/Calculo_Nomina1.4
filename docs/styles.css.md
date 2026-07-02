# styles.css

## Rol
Define la identidad visual global de la aplicación Flask (color, espaciado, cards, alerts, tablas, tabs, botones y responsive).

## Estructura
- Variables CSS en `:root` para paleta y tokens basicos.
- Variables de tema en `:root[data-theme="dark"]` para modo oscuro.
- Estilos globales de fondo y contenedores.
- Secciones, titulos y metric cards.
- Botones estandar y de descarga.
- Alertas por estado.
- Tabla y campos de formulario.
- Header con switch iOS para cambio de tema.
- Bloques de nomina por año y acordeones mensuales.
- Componentes visuales de liquidaciones (donuts de composicion y timeline).
- Ajustes responsive para movil.

## Dependencias y acoplamientos
- Acoplamiento a plantillas Jinja (`base.html`, `employee_payroll.html`, `liquidaciones.html`).
- Uso de clases semanticas propias del proyecto para reducir dependencia de estructura externa.

## Supuestos
- La paleta base prioriza contraste alto en tema claro.
- El modo oscuro mantiene contraste AA para texto principal y elementos interactivos.
- El estado del tema se persiste en navegador mediante `localStorage`.

## Vacios y riesgos
- El uso de estilos inline para algunos gradientes dinamicos (donut) depende de datos de backend validos.
- Cambios futuros de estructura de tabs/aside pueden requerir ajuste en responsive.
- No hay guia formal de diseno/versionado de estilos.
