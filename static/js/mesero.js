// ==================== MAPA DEL SALON (panel del mesero) ====================
// El estado de cada mesa lo calcula el servidor (booking/salon.py) y llega
// por /mesero/mesas/ cada 10 segundos, con su etiqueta legible incluida.
// Este archivo no decide nada sobre el estado: solo lo pinta y dispara las
// acciones (tomar, sentar invitado, liberar invitado, agregar, quitar,
// cerrar). Si el reloj avanza y una reserva entra, el proximo ciclo la
// enciende sin recargar.
(function () {
    'use strict';

    const INTERVALO_MS = 10000;

    const salon = document.getElementById('salon-mesero');
    if (!salon) {
        return; // esta pagina no es el salon del mesero
    }

    const URL_MESAS = salon.dataset.urlMesas;
    const URL_TOMAR = salon.dataset.urlTomar;
    const URL_INVITADO = salon.dataset.urlInvitado;
    const URL_CANCELAR_INVITADO = salon.dataset.urlCancelarInvitado;
    const URL_AGREGAR = salon.dataset.urlAgregar;
    const URL_QUITAR = salon.dataset.urlQuitar;
    const URL_CERRAR = salon.dataset.urlCerrar;
    const CSRF = salon.dataset.csrf;

    const grilla = document.getElementById('mapa-mesas');
    const reloj = document.getElementById('reloj-mesero');
    const aviso = document.getElementById('aviso-mesero');
    const overlay = document.getElementById('drawer-overlay');
    const drawer = document.getElementById('drawer-mesero');
    const drawerEyebrow = document.getElementById('drawer-eyebrow');
    const drawerTitulo = document.getElementById('drawer-titulo');
    const drawerCerrar = document.getElementById('drawer-cerrar');
    const drawerCuerpo = document.getElementById('drawer-cuerpo');
    const drawerResumen = document.getElementById('drawer-resumen');
    const drawerAcciones = document.getElementById('drawer-acciones');
    const nodoCarta = document.getElementById('carta-items');
    const carta = nodoCarta ? JSON.parse(nodoCarta.textContent) : [];

    let mesas = [];
    let numeroAbierto = null;

    // --- Utilidades ---
    function crear(etiqueta, clase, texto) {
        const elemento = document.createElement(etiqueta);
        if (clase) {
            elemento.className = clase;
        }
        if (texto !== undefined) {
            elemento.textContent = texto;
        }
        return elemento;
    }

    function pesos(numero) {
        return '$' + numero.toLocaleString('es-CL');
    }

    function mesaAbierta() {
        return mesas.find(function (mesa) {
            return mesa.numero === numeroAbierto;
        });
    }

    function mostrarAviso(texto, esError) {
        aviso.textContent = texto;
        aviso.hidden = false;
        aviso.classList.toggle('error', Boolean(esError));
    }

    function limpiarAviso() {
        aviso.hidden = true;
        aviso.textContent = '';
        aviso.classList.remove('error');
    }

    async function enviar(url, datos) {
        const respuesta = await fetch(url, {
            method: 'POST',
            headers: { 'X-CSRFToken': CSRF },
            body: new URLSearchParams(datos),
        });
        const cuerpo = await respuesta.json();
        if (!respuesta.ok) {
            throw new Error(cuerpo.error || 'No se pudo completar la accion.');
        }
        return cuerpo;
    }

    // --- El mapa ---
    async function cargarMapa() {
        try {
            const respuesta = await fetch(URL_MESAS);
            if (!respuesta.ok) {
                mostrarAviso('No se pudo consultar el salón.', true);
                return;
            }
            const datos = await respuesta.json();
            mesas = datos.mesas;
            reloj.textContent = datos.momento;
            pintarMapa();
            if (numeroAbierto !== null) {
                renderDrawer();
            }
        } catch (error) {
            mostrarAviso('Se perdió la conexión con el salón.', true);
        }
    }

    // La clase la resuelve el servidor: 'atendida' si la cuenta es tuya,
    // 'ajena' si la lleva otro. El JS no vuelve a decidir eso.
    function claseDeMesa(mesa) {
        return 'mesa-card mesa-' + mesa.clase + (mesa.es_grande ? ' mesa-card-grande' : '');
    }

    function pintarMapa() {
        const tarjetas = grilla.querySelectorAll('.mesa-card');
        if (tarjetas.length !== mesas.length) {
            grilla.replaceChildren.apply(grilla, mesas.map(construirTarjeta));
            return;
        }

        mesas.forEach(function (mesa, indice) {
            const tarjeta = tarjetas[indice];
            tarjeta.className = claseDeMesa(mesa);
            tarjeta.dataset.mesaNumero = mesa.numero;
            tarjeta.querySelector('[data-estado]').textContent = mesa.etiqueta;
        });
    }

    function construirTarjeta(mesa) {
        const tarjeta = crear('button', claseDeMesa(mesa));
        tarjeta.type = 'button';
        tarjeta.dataset.mesaNumero = mesa.numero;
        tarjeta.setAttribute('aria-label', 'Mesa ' + mesa.numero);

        tarjeta.appendChild(crear('span', 'mesa-card-numero', 'Mesa ' + mesa.numero));
        if (mesa.es_grande) {
            tarjeta.appendChild(crear('span', 'mesa-card-badge', 'Grande'));
        }
        tarjeta.appendChild(crear('span', 'mesa-card-meta', mesa.capacidad + ' personas · ' + mesa.ubicacion));

        const estado = crear('span', 'mesa-card-estado', mesa.etiqueta);
        estado.setAttribute('data-estado', '');
        tarjeta.appendChild(estado);

        return tarjeta;
    }

    grilla.addEventListener('click', function (evento) {
        const tarjeta = evento.target.closest('.mesa-card');
        if (!tarjeta) {
            return;
        }
        numeroAbierto = Number(tarjeta.dataset.mesaNumero);
        limpiarAviso();
        renderDrawer();
        abrirDrawer();
    });

    // --- Drawer ---
    function abrirDrawer() {
        overlay.hidden = false;
        drawer.classList.add('abierto');
        overlay.classList.add('visible');
        drawer.setAttribute('aria-hidden', 'false');
        drawerCuerpo.scrollTop = 0;
    }

    function cerrarDrawer() {
        drawer.classList.remove('abierto');
        overlay.classList.remove('visible');
        drawer.setAttribute('aria-hidden', 'true');
        numeroAbierto = null;
        setTimeout(function () {
            overlay.hidden = true;
        }, 320);
    }

    function renderDrawer() {
        const mesa = mesaAbierta();
        drawerCuerpo.replaceChildren();
        drawerAcciones.replaceChildren();
        drawerResumen.textContent = '';

        if (!mesa) {
            cerrarDrawer();
            return;
        }

        drawerTitulo.textContent = 'Mesa ' + mesa.numero;

        if (mesa.estado === 'libre') {
            drawerEyebrow.textContent = 'Sin clientes';
            pintarInvitado(mesa);
            return;
        }

        drawerEyebrow.textContent = mesa.reserva.hora_inicio + ' – ' + mesa.reserva.hora_fin;
        drawerCuerpo.appendChild(crear('p', 'drawer-nota', 'Clientes: ' + mesa.reserva.cliente));

        if (mesa.estado === 'por_atender') {
            drawerCuerpo.appendChild(crear(
                'p', 'drawer-nota',
                'Nadie ha tomado esta mesa. Tómala para abrir la cuenta.'
            ));
            const boton = crear('button', 'btn-reservar', 'Tomar mesa');
            boton.type = 'button';
            boton.addEventListener('click', function () {
                tomarMesa(mesa.numero);
            });
            drawerAcciones.appendChild(boton);

            // Un invitado que nadie tomo puede haberse ido: el mesero libera
            // la mesa. La reserva de un cliente no se cancela desde aca.
            if (mesa.reserva.es_invitado) {
                const liberar = crear('button', 'btn-volver', 'Cancelar reserva de invitado');
                liberar.type = 'button';
                liberar.addEventListener('click', function () {
                    cancelarInvitado(mesa.numero);
                });
                drawerAcciones.appendChild(liberar);
            }
            return;
        }

        // Atendida: la propia se opera, la ajena se mira.
        if (mesa.orden.es_mia) {
            pintarCuentaPropia(mesa.orden);
        } else {
            pintarCuentaAjena(mesa.orden);
        }
    }

    // Mesa libre: el mesero puede sentar a un invitado sin cuenta. El rango
    // lo resuelve el servidor (bloque en curso hasta el proximo compromiso
    // de la mesa) y viaja en `mesa.invitado`: aqui solo se pinta, incluido
    // el motivo cuando no se puede sentar a nadie.
    function pintarInvitado(mesa) {
        const invitado = mesa.invitado;

        if (mesa.proxima_reserva) {
            drawerCuerpo.appendChild(crear(
                'p', 'drawer-nota',
                'Próxima reserva: ' + mesa.proxima_reserva.hora_inicio +
                ' – ' + mesa.proxima_reserva.hora_fin +
                ' (' + mesa.proxima_reserva.cliente + ')'
            ));
        }

        if (invitado.motivo) {
            drawerCuerpo.appendChild(crear('p', 'aviso-bloqueo', invitado.motivo));
            return;
        }

        drawerCuerpo.appendChild(crear(
            'p', 'drawer-nota',
            'Sin clientes. Puedes sentar a un invitado desde ahora (' +
            invitado.inicio + ') y elegir hasta qué hora se queda.'
        ));

        drawerCuerpo.appendChild(crear('h4', 'drawer-subtitulo', '¿Hasta qué hora?'));

        const opciones = crear('div', 'carta-drawer');
        invitado.fines.forEach(function (fin) {
            const boton = crear('button', 'carta-item');
            boton.type = 'button';
            boton.appendChild(crear('span', 'carta-item-nombre', invitado.inicio + ' – ' + fin));
            boton.appendChild(crear('span', 'carta-item-meta', 'Sentar invitado y abrir cuenta'));
            boton.addEventListener('click', function () {
                sentarInvitado(mesa.numero, fin);
            });
            opciones.appendChild(boton);
        });
        drawerCuerpo.appendChild(opciones);
    }

    function pintarCuentaPropia(orden) {
        const lista = crear('ul', 'lineas-orden');
        if (!orden.lineas.length) {
            lista.appendChild(crear('li', 'panel-vacio', 'La cuenta está vacía. Agrega platos abajo.'));
        }
        orden.lineas.forEach(function (linea) {
            lista.appendChild(filaDeLinea(linea, true));
        });
        drawerCuerpo.appendChild(lista);

        drawerCuerpo.appendChild(crear('h4', 'drawer-subtitulo', 'Agregar plato'));
        drawerCuerpo.appendChild(construirCarta(orden));

        drawerResumen.textContent = 'Total: ' + pesos(orden.total);

        const cerrar = crear('button', 'btn-volver', 'Cerrar cuenta');
        cerrar.type = 'button';
        cerrar.addEventListener('click', function () {
            cerrarCuenta(orden.id);
        });
        drawerAcciones.appendChild(cerrar);
    }

    // Cuenta de otro mesero: se ve que se pidio y nada mas. Sin carta, sin
    // boton de cerrar y sin poder quitar lineas. El servidor rechazaria
    // cualquiera de esas acciones con 403; aqui simplemente no se ofrecen.
    function pintarCuentaAjena(orden) {
        const lista = crear('ul', 'lineas-orden');
        if (!orden.lineas.length) {
            lista.appendChild(crear('li', 'panel-vacio', 'Esta cuenta todavía no tiene platos.'));
        }
        orden.lineas.forEach(function (linea) {
            lista.appendChild(filaDeLinea(linea, false));
        });
        drawerCuerpo.appendChild(lista);

        drawerResumen.textContent = 'Total: ' + pesos(orden.total);
        drawerAcciones.appendChild(crear('span', 'chip-mesero', 'Atendido por: ' + orden.mesero));
    }

    function filaDeLinea(linea, conAcciones) {
        const fila = crear('li', conAcciones ? 'linea-orden' : 'linea-orden sin-accion');

        const datos = crear('div', 'linea-orden-datos');
        datos.appendChild(crear('span', 'linea-orden-nombre', linea.cantidad + ' × ' + linea.nombre));
        datos.appendChild(crear('span', 'linea-orden-meta', pesos(linea.precio_unitario) + ' c/u'));
        fila.appendChild(datos);

        fila.appendChild(crear('span', 'linea-orden-subtotal', pesos(linea.subtotal)));

        if (!conAcciones) {
            return fila;
        }

        const quitar = crear('button', 'btn-quitar', '−');
        quitar.type = 'button';
        quitar.setAttribute('aria-label', 'Quitar ' + linea.nombre);
        quitar.addEventListener('click', function () {
            quitarItem(linea.item);
        });
        fila.appendChild(quitar);

        return fila;
    }

    function construirCarta(orden) {
        const contenedor = crear('div', 'carta-drawer');
        carta.forEach(function (plato) {
            const boton = crear('button', 'carta-item');
            boton.type = 'button';
            boton.appendChild(crear('span', 'carta-item-nombre', plato.nombre));
            boton.appendChild(crear('span', 'carta-item-meta', plato.categoria + ' · ' + pesos(plato.precio)));
            boton.addEventListener('click', function () {
                agregarItem(orden.id, plato.id);
            });
            contenedor.appendChild(boton);
        });
        return contenedor;
    }

    // --- Acciones ---
    async function tomarMesa(numero) {
        limpiarAviso();
        try {
            await enviar(URL_TOMAR, { mesa: numero });
            mostrarAviso('Mesa ' + numero + ' tomada. Ya puedes agregar platos.');
        } catch (error) {
            mostrarAviso(error.message, true);
        }
        await cargarMapa();
    }

    // Un solo paso: el servidor crea la reserva del invitado y abre la
    // cuenta. Si cualquiera de las dos falla, el mesero lee el motivo.
    async function sentarInvitado(numero, horaFin) {
        limpiarAviso();
        try {
            await enviar(URL_INVITADO, { mesa: numero, hora_fin: horaFin });
            mostrarAviso('Mesa ' + numero + ' sentada para invitado hasta las ' + horaFin + '.');
        } catch (error) {
            mostrarAviso(error.message, true);
        }
        await cargarMapa();
    }

    async function cancelarInvitado(numero) {
        limpiarAviso();
        try {
            await enviar(URL_CANCELAR_INVITADO, { mesa: numero });
            mostrarAviso('Mesa ' + numero + ' liberada.');
            cerrarDrawer();
        } catch (error) {
            mostrarAviso(error.message, true);
        }
        await cargarMapa();
    }

    async function agregarItem(orden, item) {
        limpiarAviso();
        try {
            await enviar(URL_AGREGAR, { orden: orden, item: item });
        } catch (error) {
            mostrarAviso(error.message, true);
        }
        await cargarMapa();
    }

    async function quitarItem(item) {
        limpiarAviso();
        const mesa = mesaAbierta();
        if (!mesa || !mesa.orden) {
            return;
        }
        try {
            await enviar(URL_QUITAR, { orden: mesa.orden.id, item: item });
        } catch (error) {
            mostrarAviso(error.message, true);
        }
        await cargarMapa();
    }

    async function cerrarCuenta(orden) {
        limpiarAviso();
        try {
            await enviar(URL_CERRAR, { orden: orden });
            mostrarAviso('Cuenta cerrada.');
            cerrarDrawer();
        } catch (error) {
            mostrarAviso(error.message, true);
        }
        await cargarMapa();
    }

    // --- Eventos del drawer ---
    drawerCerrar.addEventListener('click', cerrarDrawer);
    overlay.addEventListener('click', cerrarDrawer);
    document.addEventListener('keydown', function (evento) {
        if (evento.key === 'Escape' && drawer.classList.contains('abierto')) {
            cerrarDrawer();
        }
    });

    // --- Arranque ---
    cargarMapa();
    setInterval(cargarMapa, INTERVALO_MS);
})();
