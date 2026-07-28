(function () {
    "use strict";

    const root = document.querySelector(".agenda-page");
    const calendarEl = document.getElementById("agendaCalendar");
    if (!root || !calendarEl || typeof FullCalendar === "undefined") {
        return;
    }

    const eventsUrl = root.dataset.eventsUrl;
    const schedeUrl = root.dataset.schedeUrl;
    const eventUrlTemplate = root.dataset.eventUrlTemplate;
    const defaultColor = root.dataset.coloreDefault || "#3b82f6";
    const subtitleEl = document.getElementById("agendaSubtitle");
    const typeButtons = root.querySelectorAll("[data-agenda-type]");

    const modalEl = document.getElementById("agendaEventModal");
    const form = document.getElementById("agendaEventForm");
    const titleEl = document.getElementById("agendaEventModalTitle");
    const idInput = document.getElementById("eventoId");
    const titoloInput = document.getElementById("eventoTitolo");
    const inizioInput = document.getElementById("eventoInizio");
    const fineInput = document.getElementById("eventoFine");
    const allDayInput = document.getElementById("eventoTuttoGiorno");
    const luogoInput = document.getElementById("eventoLuogo");
    const descrizioneInput = document.getElementById("eventoDescrizione");
    const coloreInput = document.getElementById("eventoColore");
    const coloriEl = document.getElementById("eventoColori");
    const errorEl = document.getElementById("agendaEventError");
    const deleteBtn = document.getElementById("agendaDeleteEvent");
    const newBtn = document.getElementById("agendaNewEvent");
    const cancelBtns = modalEl
        ? modalEl.querySelectorAll("[data-agenda-dismiss], [data-bs-dismiss='modal']")
        : [];

    let calendarType = "eventi";
    const ALLOWED_VIEWS = {
        dayGridMonth: true,
        timeGridWeek: true,
        timeGridDay: true,
        listWeek: true,
    };

    function readUrlState() {
        const state = {
            tipo: "eventi",
            vista: window.matchMedia("(max-width: 768px)").matches
                ? "timeGridDay"
                : "dayGridMonth",
            data: null,
        };
        try {
            const params = new URLSearchParams(window.location.search);
            const tipo = (params.get("tipo") || "").trim();
            if (tipo === "schede" || tipo === "eventi") {
                state.tipo = tipo;
            }
            const vista = (params.get("vista") || "").trim();
            if (ALLOWED_VIEWS[vista]) {
                state.vista = vista;
            }
            const data = (params.get("data") || "").trim();
            if (/^\d{4}-\d{2}-\d{2}$/.test(data)) {
                state.data = data;
            }
        } catch (error) {
            /* ignore */
        }
        return state;
    }

    const urlState = readUrlState();
    calendarType = urlState.tipo;

    function formatDateParam(date) {
        if (!(date instanceof Date) || Number.isNaN(date.getTime())) {
            return "";
        }
        return (
            date.getFullYear() +
            "-" +
            pad(date.getMonth() + 1) +
            "-" +
            pad(date.getDate())
        );
    }

    function syncUrlState() {
        try {
            const url = new URL(window.location.href);
            if (calendarType === "schede") {
                url.searchParams.set("tipo", "schede");
            } else {
                url.searchParams.delete("tipo");
            }
            const viewType = calendar.view && calendar.view.type;
            if (ALLOWED_VIEWS[viewType]) {
                url.searchParams.set("vista", viewType);
            }
            const currentStart = calendar.view && calendar.view.currentStart;
            const data = formatDateParam(currentStart);
            if (data) {
                url.searchParams.set("data", data);
            }
            window.history.replaceState({}, "", url.pathname + url.search);
        } catch (error) {
            /* ignore */
        }
    }

    function buildSchedaReturnQuery() {
        const params = new URLSearchParams();
        params.set("from", "agenda");
        params.set("tipo", calendarType === "schede" ? "schede" : "eventi");
        const viewType = calendar.view && calendar.view.type;
        if (ALLOWED_VIEWS[viewType]) {
            params.set("vista", viewType);
        }
        const currentStart = calendar.view && calendar.view.currentStart;
        const data = formatDateParam(currentStart);
        if (data) {
            params.set("data", data);
        }
        return params.toString();
    }

    const ModalCtor =
        (window.bootstrap && window.bootstrap.Modal) ||
        (window.tabler && window.tabler.Modal) ||
        null;

    if (modalEl && modalEl.parentElement !== document.body) {
        document.body.appendChild(modalEl);
    }

    let modal = null;
    if (ModalCtor && modalEl) {
        modal = ModalCtor.getOrCreateInstance
            ? ModalCtor.getOrCreateInstance(modalEl)
            : new ModalCtor(modalEl);
    }

    function showModal() {
        if (modal) {
            modal.show();
            return;
        }
        modalEl.classList.add("show");
        modalEl.style.display = "block";
        modalEl.removeAttribute("aria-hidden");
        modalEl.setAttribute("aria-modal", "true");
        document.body.classList.add("modal-open");
        let backdrop = document.getElementById("agendaEventBackdrop");
        if (!backdrop) {
            backdrop = document.createElement("div");
            backdrop.id = "agendaEventBackdrop";
            backdrop.className = "modal-backdrop fade show";
            document.body.appendChild(backdrop);
        }
    }

    function hideModal() {
        if (modal) {
            modal.hide();
            return;
        }
        modalEl.classList.remove("show");
        modalEl.style.display = "none";
        modalEl.setAttribute("aria-hidden", "true");
        modalEl.removeAttribute("aria-modal");
        document.body.classList.remove("modal-open");
        const backdrop = document.getElementById("agendaEventBackdrop");
        if (backdrop) backdrop.remove();
    }

    function csrfToken() {
        const input =
            (form && form.querySelector("[name=csrfmiddlewaretoken]")) ||
            document.querySelector("[name=csrfmiddlewaretoken]");
        if (input && input.value) {
            return input.value;
        }
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : "";
    }

    function eventUrl(id) {
        return eventUrlTemplate.replace("/0/", "/" + id + "/");
    }

    function pad(n) {
        return String(n).padStart(2, "0");
    }

    function toLocalInputValue(date, allDay) {
        if (!(date instanceof Date) || Number.isNaN(date.getTime())) {
            return "";
        }
        if (allDay) {
            return (
                date.getFullYear() +
                "-" +
                pad(date.getMonth() + 1) +
                "-" +
                pad(date.getDate())
            );
        }
        return (
            date.getFullYear() +
            "-" +
            pad(date.getMonth() + 1) +
            "-" +
            pad(date.getDate()) +
            "T" +
            pad(date.getHours()) +
            ":" +
            pad(date.getMinutes())
        );
    }

    function fromLocalInputValue(value) {
        if (!value) {
            return null;
        }
        const date = new Date(value);
        return Number.isNaN(date.getTime()) ? null : date;
    }

    function showError(message) {
        if (!errorEl) {
            return;
        }
        if (message) {
            errorEl.textContent = message;
            errorEl.classList.remove("d-none");
        } else {
            errorEl.textContent = "";
            errorEl.classList.add("d-none");
        }
    }

    function selectColor(color) {
        const value = color || defaultColor;
        coloreInput.value = value;
        coloriEl.querySelectorAll(".agenda-color-swatch").forEach(function (btn) {
            btn.classList.toggle("is-selected", btn.dataset.color === value);
        });
    }

    function setAllDayMode(allDay) {
        inizioInput.type = allDay ? "date" : "datetime-local";
        fineInput.type = allDay ? "date" : "datetime-local";
        if (allDay) {
            if (inizioInput.value.includes("T")) {
                inizioInput.value = inizioInput.value.slice(0, 10);
            }
            if (fineInput.value.includes("T")) {
                fineInput.value = fineInput.value.slice(0, 10);
            }
        } else {
            if (inizioInput.value && !inizioInput.value.includes("T")) {
                inizioInput.value += "T09:00";
            }
            if (fineInput.value && !fineInput.value.includes("T")) {
                fineInput.value += "T10:00";
            }
        }
    }

    function openModal(opts) {
        const options = opts || {};
        showError("");
        idInput.value = options.id || "";
        titoloInput.value = options.titolo || "";
        luogoInput.value = options.luogo || "";
        descrizioneInput.value = options.descrizione || "";
        allDayInput.checked = !!options.allDay;
        setAllDayMode(allDayInput.checked);
        inizioInput.value = options.inizio || "";
        fineInput.value = options.fine || "";
        selectColor(options.colore || defaultColor);
        titleEl.textContent = options.id ? "Modifica evento" : "Nuovo evento";
        deleteBtn.classList.toggle("d-none", !options.id);
        showModal();
        window.setTimeout(function () {
            titoloInput.focus();
        }, 150);
    }

    async function api(url, method, body) {
        const response = await fetch(url, {
            method: method,
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken(),
                Accept: "application/json",
            },
            body: body ? JSON.stringify(body) : undefined,
            credentials: "same-origin",
        });
        let data = null;
        try {
            data = await response.json();
        } catch (error) {
            data = null;
        }
        if (!response.ok) {
            const message =
                (data && data.error) || "Operazione non riuscita (" + response.status + ").";
            throw new Error(message);
        }
        return data;
    }

    function payloadFromForm() {
        const allDay = allDayInput.checked;
        let inizio = inizioInput.value;
        let fine = fineInput.value;
        if (allDay) {
            inizio = inizio.slice(0, 10) + "T00:00:00";
            const fineDate = fromLocalInputValue(fine.slice(0, 10) + "T00:00:00");
            const next = fineDate ? new Date(fineDate.getTime() + 24 * 60 * 60 * 1000) : null;
            fine = next
                ? next.getFullYear() +
                  "-" +
                  pad(next.getMonth() + 1) +
                  "-" +
                  pad(next.getDate()) +
                  "T00:00:00"
                : fine.slice(0, 10) + "T00:00:00";
        } else {
            inizio = inizio.length === 16 ? inizio + ":00" : inizio;
            fine = fine.length === 16 ? fine + ":00" : fine;
        }
        return {
            titolo: titoloInput.value.trim(),
            descrizione: descrizioneInput.value.trim(),
            luogo: luogoInput.value.trim(),
            inizio: inizio,
            fine: fine,
            tutto_il_giorno: allDay,
            colore: coloreInput.value || defaultColor,
        };
    }

    function isSchedeMode() {
        return calendarType === "schede";
    }

    function applyCalendarMode() {
        const schede = isSchedeMode();
        typeButtons.forEach(function (btn) {
            btn.classList.toggle("active", btn.dataset.agendaType === calendarType);
        });
        if (newBtn) {
            newBtn.classList.toggle("d-none", schede);
        }
        if (subtitleEl) {
            subtitleEl.textContent = schede
                ? "Giorni con schede di lavorazione (per data scheda)"
                : "Calendario eventi · mese, settimana e giorno";
        }
        root.classList.toggle("is-schede-mode", schede);
        calendar.setOption("editable", !schede);
        calendar.setOption("selectable", !schede);
        calendar.removeAllEventSources();
        calendar.addEventSource(schede ? schedeUrl : eventsUrl);
    }

    const calendar = new FullCalendar.Calendar(calendarEl, {
        locale: "it",
        initialView: urlState.vista,
        initialDate: urlState.data || undefined,
        headerToolbar: {
            left: "prev,next today",
            center: "title",
            right: "dayGridMonth,timeGridWeek,timeGridDay,listWeek",
        },
        buttonText: {
            today: "Oggi",
            month: "Mese",
            week: "Settimana",
            day: "Giorno",
            list: "Agenda",
        },
        height: "auto",
        nowIndicator: true,
        navLinks: true,
        editable: !isSchedeMode(),
        selectable: !isSchedeMode(),
        selectMirror: true,
        dayMaxEvents: true,
        weekNumbers: false,
        slotMinTime: "06:00:00",
        slotMaxTime: "22:00:00",
        firstDay: 1,
        events: isSchedeMode() ? schedeUrl : eventsUrl,
        eventTimeFormat: {
            hour: "2-digit",
            minute: "2-digit",
            hour12: false,
        },
        datesSet: function () {
            syncUrlState();
        },
        select: function (info) {
            if (isSchedeMode()) {
                calendar.unselect();
                return;
            }
            openModal({
                allDay: info.allDay,
                inizio: toLocalInputValue(info.start, info.allDay),
                fine: toLocalInputValue(
                    info.allDay
                        ? new Date(info.end.getTime() - 24 * 60 * 60 * 1000)
                        : info.end,
                    info.allDay
                ),
            });
            calendar.unselect();
        },
        eventClick: function (info) {
            const props = info.event.extendedProps || {};
            if (props.tipo === "scheda" || isSchedeMode()) {
                if (props.url) {
                    const sep = props.url.indexOf("?") >= 0 ? "&" : "?";
                    window.location.href = props.url + sep + buildSchedaReturnQuery();
                }
                return;
            }
            const allDay = info.event.allDay;
            const endDate = info.event.end
                ? info.event.end
                : new Date(info.event.start.getTime() + 60 * 60 * 1000);
            openModal({
                id: info.event.id,
                titolo: info.event.title,
                descrizione: props.descrizione || "",
                luogo: props.luogo || "",
                colore: props.colore || info.event.backgroundColor || defaultColor,
                allDay: allDay,
                inizio: toLocalInputValue(info.event.start, allDay),
                fine: toLocalInputValue(
                    allDay ? new Date(endDate.getTime() - 24 * 60 * 60 * 1000) : endDate,
                    allDay
                ),
            });
        },
        eventDrop: async function (info) {
            if (isSchedeMode() || (info.event.extendedProps || {}).tipo === "scheda") {
                info.revert();
                return;
            }
            try {
                await api(eventUrl(info.event.id), "PATCH", {
                    inizio: info.event.start.toISOString(),
                    fine: (info.event.end || info.event.start).toISOString(),
                    tutto_il_giorno: info.event.allDay,
                });
            } catch (error) {
                info.revert();
                window.alert(error.message);
            }
        },
        eventResize: async function (info) {
            if (isSchedeMode() || (info.event.extendedProps || {}).tipo === "scheda") {
                info.revert();
                return;
            }
            try {
                await api(eventUrl(info.event.id), "PATCH", {
                    inizio: info.event.start.toISOString(),
                    fine: (info.event.end || info.event.start).toISOString(),
                    tutto_il_giorno: info.event.allDay,
                });
            } catch (error) {
                info.revert();
                window.alert(error.message);
            }
        },
    });

    calendar.render();
    applyCalendarMode();
    syncUrlState();

    typeButtons.forEach(function (btn) {
        btn.addEventListener("click", function () {
            const nextType = btn.dataset.agendaType;
            if (!nextType || nextType === calendarType) {
                return;
            }
            calendarType = nextType;
            applyCalendarMode();
            syncUrlState();
        });
    });

    if (newBtn) {
        newBtn.addEventListener("click", function () {
            if (isSchedeMode()) {
                return;
            }
            const start = new Date();
            start.setMinutes(0, 0, 0);
            start.setHours(start.getHours() + 1);
            const end = new Date(start.getTime() + 60 * 60 * 1000);
            openModal({
                allDay: false,
                inizio: toLocalInputValue(start, false),
                fine: toLocalInputValue(end, false),
            });
        });
    }

    cancelBtns.forEach(function (btn) {
        btn.addEventListener("click", function () {
            hideModal();
        });
    });

    allDayInput.addEventListener("change", function () {
        setAllDayMode(allDayInput.checked);
    });

    coloriEl.addEventListener("click", function (event) {
        const btn = event.target.closest(".agenda-color-swatch");
        if (!btn) {
            return;
        }
        selectColor(btn.dataset.color);
    });

    form.addEventListener("submit", async function (event) {
        event.preventDefault();
        if (isSchedeMode()) {
            return;
        }
        showError("");
        const payload = payloadFromForm();
        if (!payload.titolo) {
            showError("Inserisci un titolo.");
            return;
        }
        if (!payload.inizio || !payload.fine) {
            showError("Indica inizio e fine.");
            return;
        }
        const id = idInput.value;
        const saveBtn = document.getElementById("agendaSaveEvent");
        if (saveBtn) {
            saveBtn.disabled = true;
        }
        try {
            if (id) {
                await api(eventUrl(id), "PATCH", payload);
            } else {
                await api(eventsUrl, "POST", payload);
            }
            hideModal();
            calendar.refetchEvents();
        } catch (error) {
            showError(error.message);
        } finally {
            if (saveBtn) {
                saveBtn.disabled = false;
            }
        }
    });

    deleteBtn.addEventListener("click", async function () {
        const id = idInput.value;
        if (!id || isSchedeMode()) {
            return;
        }
        if (!window.confirm("Eliminare questo evento?")) {
            return;
        }
        try {
            await api(eventUrl(id), "DELETE");
            hideModal();
            calendar.refetchEvents();
        } catch (error) {
            showError(error.message);
        }
    });
})();
