odoo.define('bharat_ddn.mobile_mask_widget', function (require) {
    "use strict";

    var AbstractField = require('web.AbstractField');
    var fieldRegistry = require('web.field_registry');

    var MobileMaskWidget = AbstractField.extend({
        init: function () {
            this._super.apply(this, arguments);
        },

        _render: function () {
            var value = this.value;
            if (value && value.length >= 4) {
                var masked = value.substring(0, 2) + '*'.repeat(value.length - 4) + value.substring(value.length - 2);
                this.$el.text(masked);
            } else {
                this.$el.text(value || '');
            }
        }
    });

    fieldRegistry.add('mobile_mask', MobileMaskWidget);
    return MobileMaskWidget;
}); 