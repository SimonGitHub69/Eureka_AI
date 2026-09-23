(function () {
    "use strict";

    if (!document.body.classList.contains("st-embed")) {
        return;
    }

    function addEmbed(url) {
        try {
            var u = new URL(url, window.location.origin);
            if (u.origin !== window.location.origin) {
                return url;
            }
            u.searchParams.set("embed", "1");
            return u.pathname + u.search + u.hash;
        } catch (e) {
            return url;
        }
    }

    document.addEventListener(
        "click",
        function (ev) {
            if (ev.defaultPrevented || ev.button !== 0) {
                return;
            }
            if (ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) {
                return;
            }
            var link = ev.target.closest("a[href]");
            if (!link) {
                return;
            }
            var href = link.getAttribute("href");
            if (!href || href.charAt(0) === "#" || href.indexOf("javascript:") === 0) {
                return;
            }
            try {
                var u = new URL(href, window.location.origin);
                if (u.origin !== window.location.origin) {
                    return;
                }
                if (u.searchParams.get("embed") === "1") {
                    return;
                }
                ev.preventDefault();
                window.location.href = addEmbed(href);
            } catch (e) {
                /* ignore */
            }
        },
        true
    );

    document.addEventListener(
        "submit",
        function (ev) {
            var form = ev.target;
            if (!form || form.tagName !== "FORM") {
                return;
            }
            var method = (form.getAttribute("method") || "get").toLowerCase();
            if (method === "get") {
                var action = form.getAttribute("action") || window.location.href;
                form.setAttribute("action", addEmbed(action));
                if (!form.querySelector('input[name="embed"]')) {
                    var input = document.createElement("input");
                    input.type = "hidden";
                    input.name = "embed";
                    input.value = "1";
                    form.appendChild(input);
                }
            } else if (!form.querySelector('input[name="embed"]')) {
                var hidden = document.createElement("input");
                hidden.type = "hidden";
                hidden.name = "embed";
                hidden.value = "1";
                form.appendChild(hidden);
            }
        },
        true
    );
})();
