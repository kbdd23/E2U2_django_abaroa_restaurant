// ==================== SISTEMA DE FILTROS ====================
const filterCategorias = document.querySelectorAll('.filter-categoria');
const filterAlergenos = document.querySelectorAll('.filter-alergeno');
const platos = document.querySelectorAll('.plato');
const searchInput = document.getElementById('search');

// NUEVO: Identificamos el formulario de búsqueda
const searchForm = document.querySelector('.search-bar'); 

if (platos.length > 0) {

    // NUEVO: Evitamos que al presionar "Enter" la página se recargue y se cuelgue el servidor
    if (searchForm) {
        searchForm.addEventListener('submit', function(evento) {
            evento.preventDefault();
        });
    }

    function aplicarFiltros() {
        const categoriasSeleccionadas = Array.from(filterCategorias)
            .filter(cb => cb.checked)
            .map(cb => cb.value)
            .filter(valor => valor !== 'todos');

        const alejenosSeleccionados = Array.from(filterAlergenos)
            .filter(cb => cb.checked)
            .map(cb => cb.value);

        const textoBusqueda = searchInput.value.toLowerCase();

        platos.forEach(plato => {
            let mostrar = true;

            const categoria = plato.getAttribute('data-category');
            if (categoriasSeleccionadas.length > 0 && !categoriasSeleccionadas.includes(categoria)) {
                mostrar = false;
            }

            if (alejenosSeleccionados.length > 0) {
                const tags = plato.querySelectorAll('[data-alergeno]');
                const tieneAlergeno = Array.from(tags).some(tag =>
                    alejenosSeleccionados.includes(tag.getAttribute('data-alergeno'))
                );
                if (tieneAlergeno) {
                    mostrar = false;
                }
            }

            if (textoBusqueda.length > 0) {
                const nombre = plato.querySelector('h3').textContent.toLowerCase();
                const descripcion = plato.querySelector('p').textContent.toLowerCase();
                if (!nombre.includes(textoBusqueda) && !descripcion.includes(textoBusqueda)) {
                    mostrar = false;
                }
            }

            plato.style.display = mostrar ? 'flex' : 'none';
        });
    }

    filterCategorias.forEach(checkbox => {
        checkbox.addEventListener('change', aplicarFiltros);
    });

    filterAlergenos.forEach(checkbox => {
        checkbox.addEventListener('change', aplicarFiltros);
    });

    searchInput.addEventListener('input', aplicarFiltros);
}

// ==================== ALTO REAL DEL HEADER ====================
(function () {
    'use strict';

    const encabezado = document.querySelector('.site-header');
    const hero = document.querySelector('.hero-carrusel');
    if (!encabezado || !hero) {
        return; 
    }

    function publicarAltoDelHeader() {
        document.documentElement.style.setProperty(
            '--altura-header-real',
            encabezado.offsetHeight + 'px'
        );
    }

    new ResizeObserver(publicarAltoDelHeader).observe(encabezado);
    publicarAltoDelHeader();
})();