/** @odoo-module **/

// # Part of Odoo Module Developed by Bizople Solutions Pvt. Ltd.
// # See LICENSE file for full copyright and licensing details.

import { UserMenu } from "@web/webclient/user_menu/user_menu";
import { patch } from "@web/core/utils/patch";
import { user } from "@web/core/user";
import { session } from '@web/session';
import { router } from "@web/core/browser/router";

patch(UserMenu.prototype, {
    setup() {
        super.setup();
        //  greeting
        var current_time_hr = new Date().getHours().toLocaleString("en-US", { timeZone: user.tz  });
        if ((parseInt(current_time_hr) >= 6) && (parseInt(current_time_hr) < 12)){
            var greeting = "Good Morning"
        } else if ((parseInt(current_time_hr) >= 12) && parseInt(current_time_hr) <= 18) {
            var greeting = "Good Afternoon"
        } else {
            var greeting = "Good Evening"
        }
        this.greeting = greeting
    }
});
