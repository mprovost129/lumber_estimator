'use strict';

document.addEventListener('DOMContentLoaded', function () {
    var input_type_select = document.getElementById('id_input_type');
    var supported_inputs = document.querySelectorAll('input[name="supported_input_types"]');
    if (!input_type_select || !supported_inputs.length) {
        return;
    }

    var quantity_per_box_row = document.querySelector('.field-quantity_per_box');
    var lengths_group = document.getElementById('lengths-group');

    function is_supported(value) {
        return Array.prototype.some.call(supported_inputs, function (input) {
            return input.checked && input.value === value;
        });
    }

    function sync_default_options() {
        var has_selected_default = false;
        Array.prototype.forEach.call(input_type_select.options, function (option) {
            var enabled = is_supported(option.value);
            option.disabled = !enabled;
            if (option.value === input_type_select.value && enabled) {
                has_selected_default = true;
            }
        });
        if (!has_selected_default) {
            var first_enabled = Array.prototype.find.call(input_type_select.options, function (option) {
                return !option.disabled;
            });
            if (first_enabled) {
                input_type_select.value = first_enabled.value;
            }
        }
    }

    function update_visible_fields() {
        sync_default_options();

        if (quantity_per_box_row) {
            quantity_per_box_row.style.display = is_supported('box') ? '' : 'none';
        }
        if (lengths_group) {
            lengths_group.style.display = is_supported('ft') ? '' : 'none';
        }
    }

    Array.prototype.forEach.call(supported_inputs, function (input) {
        input.addEventListener('change', update_visible_fields);
    });
    update_visible_fields();
});
