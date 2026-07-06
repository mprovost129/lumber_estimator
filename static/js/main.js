// Main JavaScript entry point

(function () {
    'use strict';

    // Mobile navigation rail toggle
    var toggle = document.getElementById('rail-toggle');
    var scrim = document.getElementById('app-rail-scrim');

    function closeRail() { document.body.classList.remove('rail-open'); }

    if (toggle) {
        toggle.addEventListener('click', function () {
            document.body.classList.toggle('rail-open');
        });
    }
    if (scrim) {
        scrim.addEventListener('click', closeRail);
    }
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') { closeRail(); }
    });
})();
