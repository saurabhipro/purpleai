/** @odoo-module **/
import { Pager } from "@web/core/pager/pager";
import { patch } from "@web/core/utils/patch";
import { rpc } from "@web/core/network/rpc";

patch(Pager.prototype, {
    async setup() {
        super.setup()
        await rpc('/update/chatter/position', {}).then(function (data) {
            if ( data === 'chatter_right' ) {
                $("body").find('.chatter_position_right').addClass('active')
                $("body").find('.chatter_position_bottom').removeClass('active')
            }
            else {
                $("body").find('.chatter_position_right').removeClass('active')
                $("body").find('.chatter_position_bottom').addClass('active')
            }
        })
    },

    async updateChatterPosition (position) {
        await rpc('/update/chatter/position', {
            'chatter_position': position
        }).then(function (rec) {
            
        })
        this.chatter_position = position

        if ( position === 'chatter_right' ) {
            $("body").removeClass('chatter_bottom');
            $("body").addClass(position);
            $("body").find('.chatter_position_right').addClass('active')
            $("body").find('.chatter_position_bottom').removeClass('active')
        }
        else {
            $("body").removeClass('chatter_right');
            $("body").addClass(position);
            $("body").find('.chatter_position_right').removeClass('active')
            $("body").find('.chatter_position_bottom').addClass('active')
        }
    }
})