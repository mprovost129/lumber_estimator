'use strict';

document.addEventListener('DOMContentLoaded', function () {
    var sectionsContainer = document.getElementById('category-sections');
    if (!sectionsContainer) {
        return;
    }

    function getCookie(name) {
        var value = null;
        if (document.cookie) {
            document.cookie.split(';').forEach(function (cookie) {
                cookie = cookie.trim();
                if (cookie.indexOf(name + '=') === 0) {
                    value = decodeURIComponent(cookie.substring(name.length + 1));
                }
            });
        }
        return value;
    }
    var csrftoken = getCookie('csrftoken');

    function post(url, body) {
        fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
            body: JSON.stringify(body),
        });
    }

    if (typeof Sortable !== 'undefined') {
        // Reorder whole construction-system sections.
        Sortable.create(sectionsContainer, {
            handle: '.drag-handle-section',
            animation: 150,
            onEnd: function () {
                var order = Array.prototype.map.call(
                    sectionsContainer.querySelectorAll(':scope > .category-section'),
                    function (section) { return section.dataset.category; },
                );
                post(sectionsContainer.dataset.categoryOrderUrl, { order: order });
            },
        });

        // Reorder items within each section independently - no shared `group`
        // option between instances, so items can't be dragged across sections.
        document.querySelectorAll('.item-list').forEach(function (list) {
            Sortable.create(list, {
                handle: '.drag-handle-item',
                animation: 150,
                onEnd: function () {
                    var order = Array.prototype.map.call(
                        list.querySelectorAll('tr'),
                        function (row) { return row.dataset.role; },
                    );
                    post(list.dataset.itemOrderUrl, { category: list.dataset.category, order: order });
                },
            });
        });
    }

    document.addEventListener('change', function (event) {
        var input = event.target.closest('.material-group-waste-input');
        if (!input) {
            return;
        }
        var wastePercent = parseFloat(input.value);
        if (isNaN(wastePercent) || wastePercent < 0 || wastePercent > 100) {
            window.location.reload();
            return;
        }
        input.disabled = true;
        fetch(input.dataset.updateUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
            body: JSON.stringify({ waste_percent: wastePercent }),
        })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error('Waste update failed.');
                }
                return response.json();
            })
            .then(function () {
                window.location.reload();
            })
            .catch(function () {
                input.disabled = false;
                window.location.reload();
            });
    });
});
