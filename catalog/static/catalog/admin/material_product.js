'use strict';

document.addEventListener('DOMContentLoaded', function () {
    var input_type_select = document.getElementById('id_input_type');
    if (!input_type_select) {
        return;
    }

    var quantity_per_box_row = document.querySelector('.field-quantity_per_box');
    var lengths_group = document.getElementById('lengths-group');

    function update_visible_fields() {
        var input_type = input_type_select.value;

        if (quantity_per_box_row) {
            quantity_per_box_row.style.display = input_type === 'box' ? '' : 'none';
        }
        if (lengths_group) {
            lengths_group.style.display = input_type === 'ft' ? '' : 'none';
        }
    }

    input_type_select.addEventListener('change', update_visible_fields);
    update_visible_fields();
});
