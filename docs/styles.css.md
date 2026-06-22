# styles.css

## Rol
Define identidad visual de la aplicacion Streamlit (color, espaciado, cards, alerts, botones y responsive).

## Estructura
- Variables CSS en `:root` para paleta y tokens basicos.
- Estilos globales de fondo y contenedores.
- Secciones, titulos y metric cards.
- Botones estandar y de descarga.
- Alertas por estado.
- Tabla y campos de formulario.
- Ajustes responsive para movil.

## Dependencias y acoplamientos
- Acoplamiento fuerte a clases/estructura que Streamlit renderiza en el DOM.
- Algunos selectores usan `data-testid`, sensibles a cambios de version.

## Supuestos
- La paleta actual prioriza contraste alto y fondo claro.

## Vacios y riesgos
- Selectores muy especificos pueden romperse tras actualizaciones de Streamlit.
- No hay guia formal de diseno/versionado de estilos.
