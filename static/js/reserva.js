// ==================== WIZARD DE RESERVA: salon vivo ====================
// Flujo: grilla 4x2 (mesas del modelo) -> click -> drawer lateral ->
// dia (chips por semana) -> bloques de 1h disponibles (desde la BD) ->
// rango -> POST del form real de Django.
//
// Si el servicio de hoy ya termino (o el restaurante esta cerrado), el
// drawer salta directo al selector de dia en vez de mostrar un paso de
// bloques vacio: el usuario se ahorra el click en "Cambiar dia".
(function () {
    'use strict';

    const NOMBRES_DIAS = ['Dom', 'Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab'];
    const NOMBRES_MESES = [
        'ene', 'feb', 'mar', 'abr', 'may', 'jun',
        'jul', 'ago', 'sep', 'oct', 'nov', 'dic',
    ];
    const DOMINGO = 0; // getDay(): 0 = domingo

    const MENSAJE_HOY_CERRADO = 'Hoy no hay servicio. Elige otro día.';
    const MENSAJE_DIA_CERRADO = 'Ese día no hay servicio. Elige otro día.';

    const grillaMesas = document.getElementById('grilla-mesas');
    const drawer = document.getElementById('drawer-reserva');
    if (!grillaMesas || !drawer) {
        return; // esta pagina no es el salon de reservas
    }

    const overlay = document.getElementById('drawer-overlay');
    const drawerCuerpo = drawer.querySelector('.drawer-cuerpo');
    const drawerTitulo = document.getElementById('drawer-titulo');
    const drawerCerrar = document.getElementById('drawer-cerrar');
    const pasoFecha = document.getElementById('paso-fecha');
    const pasoBloques = document.getElementById('paso-bloques');
    const gruposFecha = document.getElementById('grupos-fecha');
    const fechaElegida = document.getElementById('fecha-elegida');
    const badgeHoy = document.getElementById('badge-hoy');
    const avisoFecha = document.getElementById('aviso-fecha');
    const resumenMesa = document.getElementById('resumen-mesa');
    const gridBloques = document.getElementById('grid-bloques');
    const pistaBloques = document.getElementById('pista-bloques');
    const fechaOtroDia = document.getElementById('fecha-otro-dia');
    const drawerResumen = document.getElementById('drawer-resumen');
    const btnVolver = document.getElementById('btn-volver');
    const btnConfirmar = document.getElementById('btn-confirmar');
    const formReal = document.getElementById('form-reserva-real');

    const URL_BLOQUES = drawer.dataset.urlBloques;

    // --- Estado del wizard ---
    const estado = {
        mesa: null, // { id, numero, capacidad, ubicacion }
        fecha: null, // 'YYYY-MM-DD'
        inicio: null, // indice sobre bloquesDelDia
        fin: null, // indice sobre bloquesDelDia
    };
    // El servicio de hoy ya termino: hoy deja de ofrecerse como dia.
    let hoyCerrado = false;

    // Todos los bloques del dia consultado, libres y ocupados:
    // { inicio: 'HH:MM', fin: 'HH:MM', libre: bool, boton: <button> }.
    // Se indexa por posicion real en el horario, no por bloque libre:
    // un rango valido no puede saltarse un bloque ocupado intermedio.
    let bloquesDelDia = [];

    // --- Utilidades de fecha (siempre hora local) ---
    function aCadena(fecha) {
        const mes = String(fecha.getMonth() + 1).padStart(2, '0');
        const dia = String(fecha.getDate()).padStart(2, '0');
        return fecha.getFullYear() + '-' + mes + '-' + dia;
    }

    function inicioDeHoy() {
        const hoy = new Date();
        hoy.setHours(0, 0, 0, 0);
        return hoy;
    }

    function sumarDias(fecha, cantidad) {
        const copia = new Date(fecha);
        copia.setDate(copia.getDate() + cantidad);
        return copia;
    }

    function esDiaHabil(fecha) {
        return fecha.getDay() !== DOMINGO;
    }

    // Lunes de la semana a la que pertenece la fecha (semana ISO).
    function lunesDeSemana(fecha) {
        const copia = new Date(fecha);
        copia.setDate(copia.getDate() - ((copia.getDay() + 6) % 7));
        return copia;
    }

    function fechaLegible(cadena) {
        const fecha = new Date(cadena + 'T00:00:00');
        return NOMBRES_DIAS[fecha.getDay()] + ' ' + fecha.getDate() + ' ' +
            NOMBRES_MESES[fecha.getMonth()];
    }

    // Fecha legible del encabezado + distintivo "HOY": el badge aparece
    // solo cuando la disponibilidad mostrada es del dia en curso.
    function mostrarFechaElegida(cadenaFecha) {
        fechaElegida.textContent = fechaLegible(cadenaFecha);
        badgeHoy.hidden = cadenaFecha !== aCadena(new Date());
    }

    // --- Drawer: abrir / cerrar ---
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
        quitarMarcaEnGrilla();
        setTimeout(function () {
            overlay.hidden = true;
        }, 320);
    }

    function quitarMarcaEnGrilla() {
        const marcada = grillaMesas.querySelector('.mesa-card.seleccionada');
        if (marcada) {
            marcada.classList.remove('seleccionada');
        }
    }

    // --- Paso 1: grilla -> click en mesa ---
    grillaMesas.addEventListener('click', function (evento) {
        const card = evento.target.closest('.mesa-card');
        if (!card) {
            return;
        }

        estado.mesa = {
            id: card.dataset.mesaId,
            numero: card.dataset.mesaNumero,
            capacidad: card.dataset.mesaCapacidad,
            ubicacion: card.dataset.mesaUbicacion,
        };
        // El salon abre directo con la disponibilidad de HOY: reservar es
        // lo mas comun para el dia en curso. El boton "Cambiar dia" del pie
        // lleva al selector de fechas (chips de esta semana + otro dia).
        const hoy = new Date();
        estado.fecha = aCadena(hoy);
        estado.inicio = null;
        estado.fin = null;
        bloquesDelDia = [];

        quitarMarcaEnGrilla();
        card.classList.add('seleccionada');
        drawerTitulo.textContent = 'Mesa ' + estado.mesa.numero;
        drawerResumen.textContent = '';
        fechaOtroDia.value = '';
        abrirDrawer();

        // El servicio de hoy ya termino: se salta el paso vacio y se ofrece
        // el selector de dia de una vez.
        if (hoyCerrado) {
            irAPasoFecha(mensajeDeCierre());
            return;
        }

        pasoFecha.hidden = true;
        pasoBloques.hidden = false;
        btnVolver.hidden = false;
        btnConfirmar.disabled = true;
        mostrarFechaElegida(estado.fecha);
        marcarFechaEnChips(null);
        cargarBloques();
    });

    // --- Paso 2: seleccion de dia ---
    function renderFechas() {
        const hoy = inicioDeHoy();
        const lunesProximo = sumarDias(lunesDeSemana(hoy), 7);
        const dias = [];

        // Solo esta semana (de hoy al sabado): fechas mas lejanas van por
        // el datepicker "Buscar otro dia", sin llenar el panel de opciones.
        for (let offset = 0; ; offset++) {
            const dia = sumarDias(hoy, offset);
            if (dia >= lunesProximo) {
                break; // se acabo esta semana
            }
            if (!esDiaHabil(dia)) {
                continue; // domingo cerrado: no se ofrece
            }
            if (offset === 0 && hoyCerrado) {
                continue; // hoy ya no tiene servicio
            }
            dias.push(dia);
        }

        gruposFecha.innerHTML = '';

        if (!dias.length) {
            const aviso = document.createElement('p');
            aviso.className = 'pista-fecha';
            aviso.textContent = 'Esta semana no quedan dias para reservar: busca otra fecha abajo.';
            gruposFecha.appendChild(aviso);
            return;
        }

        const grupo = document.createElement('div');
        grupo.className = 'grupo-semana';

        const rotulo = document.createElement('span');
        rotulo.className = 'grupo-semana-label';
        rotulo.textContent = 'Esta semana';
        grupo.appendChild(rotulo);

        const contenedorChips = document.createElement('div');
        contenedorChips.className = 'chips-fecha';
        dias.forEach(function (dia) {
            contenedorChips.appendChild(chipDeDia(dia));
        });
        grupo.appendChild(contenedorChips);
        gruposFecha.appendChild(grupo);
    }

    function chipDeDia(fecha) {
        const boton = document.createElement('button');
        boton.type = 'button';
        boton.className = 'chip-dia';
        boton.dataset.fecha = aCadena(fecha);
        boton.innerHTML =
            '<span class="chip-dia-nombre">' + NOMBRES_DIAS[fecha.getDay()] + '</span>' +
            '<span class="chip-dia-numero">' + fecha.getDate() + '</span>' +
            '<span class="chip-dia-mes">' + NOMBRES_MESES[fecha.getMonth()] + '</span>';
        boton.addEventListener('click', function () {
            elegirFecha(boton.dataset.fecha);
        });
        return boton;
    }

    function marcarFechaEnChips(cadenaFecha) {
        const chips = gruposFecha.querySelectorAll('.chip-dia');
        chips.forEach(function (chip) {
            chip.classList.toggle('seleccionado', chip.dataset.fecha === cadenaFecha);
        });
    }

    function elegirFecha(cadenaFecha) {
        estado.fecha = cadenaFecha;
        estado.inicio = null;
        estado.fin = null;
        marcarFechaEnChips(cadenaFecha);
        mostrarFechaElegida(cadenaFecha);
        btnVolver.hidden = false;
        cargarBloques();
    }

    // Datepicker "buscar otro dia": respeta el horario real (domingo cerrado).
    fechaOtroDia.addEventListener('change', function () {
        const valor = fechaOtroDia.value;
        if (!valor) {
            return;
        }
        if (new Date(valor + 'T00:00:00').getDay() === DOMINGO) {
            fechaOtroDia.setCustomValidity('El restaurante cierra los domingos.');
            fechaOtroDia.reportValidity();
            return;
        }
        fechaOtroDia.setCustomValidity('');
        elegirFecha(valor);
    });

    // --- Paso 3: bloques disponibles (la BD responde) ---
    function cargarBloques() {
        gridBloques.innerHTML = '';
        pistaBloques.textContent = 'Consultando disponibilidad...';
        btnConfirmar.disabled = true;
        drawerResumen.textContent = '';
        pasoBloques.hidden = false;
        pasoFecha.hidden = true;
        drawerCuerpo.scrollTop = 0;

        const consulta = URL_BLOQUES + '?mesa=' + encodeURIComponent(estado.mesa.id) +
            '&fecha=' + encodeURIComponent(estado.fecha);

        fetch(consulta)
            .then(function (respuesta) {
                return respuesta.json().then(function (datos) {
                    return { ok: respuesta.ok, datos: datos };
                });
            })
            .then(function (resultado) {
                if (!resultado.ok) {
                    // El restaurante esta cerrado ese dia: al selector.
                    marcarCerrado();
                    irAPasoFecha(mensajeDeCierre());
                    return;
                }
                renderBloques(resultado.datos.bloques);
            })
            .catch(function () {
                pistaBloques.textContent = 'Error de conexion. Intenta de nuevo.';
            });
    }

    function renderBloques(bloques) {
        // Sin bloques = sin servicio: en vez de un paso vacio, el selector
        // de dia (es el mismo caso que un domingo).
        if (!bloques.length) {
            marcarCerrado();
            irAPasoFecha(mensajeDeCierre());
            return;
        }

        resumenMesa.textContent = 'Mesa ' + estado.mesa.numero + ' · ' +
            estado.mesa.capacidad + ' personas · ' + estado.mesa.ubicacion;

        gridBloques.innerHTML = '';
        bloquesDelDia = [];

        bloques.forEach(function (bloque) {
            const boton = document.createElement('button');
            boton.type = 'button';
            boton.className = 'bloque' + (bloque.libre ? '' : ' ocupado');
            boton.textContent = bloque.inicio + ' - ' + bloque.fin;
            boton.disabled = !bloque.libre;

            bloquesDelDia.push({
                inicio: bloque.inicio,
                fin: bloque.fin,
                libre: bloque.libre,
                boton: boton,
            });
            gridBloques.appendChild(boton);
        });

        bloquesDelDia.forEach(function (entrada, indice) {
            if (entrada.libre) {
                entrada.boton.addEventListener('click', function () {
                    seleccionarBloque(indice);
                });
            }
        });

        pistaBloques.textContent =
            'Toca un bloque para reservar 1 hora, o encadena bloques consecutivos libres para un rango mayor.';
        pintarSeleccion();
    }

    // Seleccion de rango entre dos extremos (patron interruptor):
    // - Sin seleccion: el bloque tocado se enciende como unico extremo.
    // - Con un extremo encendido: tocarlo de nuevo lo apaga (toggle); tocar
    //   otro bloque libre forma el rango si todos los intermedios estan
    //   libres — si hay un hueco reservado, el nuevo extremo no se enciende
    //   y la pista avisa.
    // - Con rango definido: cualquier toque reinicia la seleccion desde el
    //   bloque tocado.
    function seleccionarBloque(indice) {
        const hayInicio = estado.inicio !== null;
        const hayRangoCompleto = hayInicio && estado.fin !== null;

        if (hayRangoCompleto) {
            // Tercer toque (rango ya definido): reinicia desde este bloque.
            estado.inicio = indice;
            estado.fin = null;
            pistaBloques.textContent = '';
        } else if (hayInicio) {
            if (indice === estado.inicio) {
                // Toggle: el unico bloque encendido se apaga.
                estado.inicio = null;
                pistaBloques.textContent = '';
            } else {
                const menor = Math.min(estado.inicio, indice);
                const mayor = Math.max(estado.inicio, indice);
                if (esRangoContiguoLibre(menor, mayor)) {
                    estado.inicio = menor;
                    estado.fin = mayor;
                    pistaBloques.textContent = '';
                } else {
                    // Hueco ocupado en medio: no se enciende el extremo.
                    pistaBloques.textContent =
                        'No puedes saltar un bloque ya reservado: elige un rango de bloques consecutivos libres.';
                }
            }
        } else {
            estado.inicio = indice;
            pistaBloques.textContent = '';
        }
        pintarSeleccion();
    }

    function esRangoContiguoLibre(desde, hasta) {
        for (let i = desde; i <= hasta; i++) {
            if (!bloquesDelDia[i].libre) {
                return false;
            }
        }
        return true;
    }

    function pintarSeleccion() {
        bloquesDelDia.forEach(function (entrada, indice) {
            const boton = entrada.boton;
            boton.classList.remove('sel-inicio', 'sel-medio', 'sel-fin');
            if (estado.inicio === null) {
                return;
            }
            const dentroDeRango = estado.fin !== null
                ? indice >= estado.inicio && indice <= estado.fin
                : indice === estado.inicio;
            if (dentroDeRango) {
                boton.classList.add(
                    estado.fin === null || indice === estado.inicio ? 'sel-inicio' :
                    indice === estado.fin ? 'sel-fin' : 'sel-medio'
                );
            }
        });
        actualizarResumen();
    }

    function actualizarResumen() {
        if (estado.inicio === null) {
            btnConfirmar.disabled = true;
            drawerResumen.textContent = '';
            return;
        }

        // Un solo bloque (inicio sin fin) ya es una reserva valida de 1 hora:
        // Confirmar la cierra, o el usuario extiende el rango tocando otro
        // bloque libre consecutivo.
        const bloqueInicio = bloquesDelDia[estado.inicio];
        const inicio = bloqueInicio.inicio;
        const fin = estado.fin === null
            ? bloqueInicio.fin
            : bloquesDelDia[estado.fin].fin;
        btnConfirmar.disabled = false;
        drawerResumen.textContent = 'Mesa ' + estado.mesa.numero + ' · ' +
            fechaLegible(estado.fecha) + ' · ' + inicio + ' - ' + fin;
    }

    // --- Confirmar: rellena el form real y hace POST ---
    btnConfirmar.addEventListener('click', function () {
        if (estado.inicio === null) {
            return;
        }
        const bloqueInicio = bloquesDelDia[estado.inicio];
        const inicio = bloqueInicio.inicio;
        const fin = estado.fin === null
            ? bloqueInicio.fin
            : bloquesDelDia[estado.fin].fin;

        formReal.elements['mesa'].value = estado.mesa.id;
        formReal.elements['fecha'].value = estado.fecha;
        formReal.elements['hora_inicio'].value = inicio;
        formReal.elements['hora_fin'].value = fin;
        formReal.submit();
    });

    // --- Ir al selector de dia (con aviso opcional) ---
    function irAPasoFecha(mensaje) {
        estado.inicio = null;
        estado.fin = null;
        pasoBloques.hidden = true;
        pasoFecha.hidden = false;
        btnVolver.hidden = true;
        btnConfirmar.disabled = true;
        drawerResumen.textContent = '';
        fechaOtroDia.value = '';
        // Si hoy ya no tiene servicio, el datepicker arranca en manana.
        fechaOtroDia.min = aCadena(hoyCerrado ? sumarDias(inicioDeHoy(), 1) : inicioDeHoy());
        renderFechas();
        marcarFechaEnChips(estado.fecha);
        avisoFecha.textContent = mensaje || '';
        avisoFecha.hidden = !mensaje;
        drawerCuerpo.scrollTop = 0;
    }

    // Marca que el dia consultado (si es hoy) ya no tiene servicio.
    function marcarCerrado() {
        if (estado.fecha === aCadena(new Date())) {
            hoyCerrado = true;
        }
    }

    function mensajeDeCierre() {
        return estado.fecha === aCadena(new Date())
            ? MENSAJE_HOY_CERRADO
            : MENSAJE_DIA_CERRADO;
    }

    // --- Acciones del drawer ---
    drawerCerrar.addEventListener('click', cerrarDrawer);
    overlay.addEventListener('click', cerrarDrawer);
    btnVolver.addEventListener('click', function () {
        // "Cambiar dia": del paso de bloques al selector de fechas.
        // estado.fecha se conserva para marcar el dia en curso.
        irAPasoFecha();
    });

    document.addEventListener('keydown', function (evento) {
        if (evento.key === 'Escape' && drawer.classList.contains('abierto')) {
            cerrarDrawer();
        }
    });
})();
