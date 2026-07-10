// Filters a stock-length <select> (options valued by MaterialLength id) down
// to the options belonging to whichever MaterialProduct a paired material
// <select> currently has chosen. Shared between the manual line-item form
// (estimate_detail.html) and the assembly-builder rule rows (assembly_form.html),
// both of which render a `material-lengths-data` json_script block from the
// same `material_lengths_data` context value.
(function () {
    var lengthsById = null;

    function loadLengthsById() {
        if (lengthsById) {
            return lengthsById;
        }
        lengthsById = {};
        var node = document.getElementById('material-lengths-data');
        if (node) {
            (JSON.parse(node.textContent) || []).forEach(function (length) {
                lengthsById[String(length.id)] = length;
            });
        }
        return lengthsById;
    }

    function filterLengthOptions(materialSelect, lengthSelect, opts) {
        opts = opts || {};
        var lengths = loadLengthsById();
        var materialId = materialSelect.value;
        var selectedStillValid = false;
        var defaultOptionValue = '';

        Array.prototype.forEach.call(lengthSelect.options, function (option) {
            if (!option.value) {
                return; // always keep the blank "---------" option visible
            }
            var length = lengths[option.value];
            var visible = !!length && String(length.product_id) === String(materialId);
            option.hidden = !visible;
            option.disabled = !visible;
            if (visible && option.value === lengthSelect.value) {
                selectedStillValid = true;
            }
            if (visible && length.is_default) {
                defaultOptionValue = option.value;
            }
        });

        if (!selectedStillValid) {
            lengthSelect.value = opts.preselectDefault ? defaultOptionValue : '';
        }
    }

    window.materialLengthFilter = {filterLengthOptions: filterLengthOptions};
})();
