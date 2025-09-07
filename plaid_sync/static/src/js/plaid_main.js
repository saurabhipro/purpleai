/** @odoo-module **/


import { loadJS } from '@web/core/assets';
import { Component, onWillStart } from "@odoo/owl";
import { useService } from '@web/core/utils/hooks';
import { registry } from "@web/core/registry";

class PlaidAccountConfigurationWidget extends Component{
        debugger;
        on_attach() {
            if (this.exit === true) {
                this.do_action({type: 'ir.actions.act_window_close'});
            }

        }

        setup() {
        debugger;
        this.orm = useService("orm");
            this.context = this.props.action.context
            this.rec_id = this.context.rec_id;
            this.plaid_client = this.context.plaid_client;
            this.plaid_secret = this.context.plaid_secret;
            this.environment = this.context.environment;
            this.token_key = false;
            this.loaded = new Promise(function (resolve) {
                self._loadedResolver = resolve;
            });
            onWillStart (async()=>{

                var self=this;
                var token = self.make_token();

                $.when(token,loadJS('https://cdn.plaid.com/link/v2/stable/link-initialize.js')).then(function() {
                    var plaid_options = {
                        env: self.environment,
                        token: self.token_key,
                        onSuccess: function(public_token, metadata) {
                            if (self.public_token === undefined) {
                                return self.linkSuccess(public_token, metadata);
                            }
                            else {
                                self.exit = true;
                                self._loadedResolver();
                                location.reload();
                            }
                        },
                        onEvent: function(eventName, metadata) {
                           console.log('event');
                           console.log(eventName, metadata);
                        },

                        onExit: function(err, metadata) {
                            if (err) {
                                console.log(err);
                                console.log(metadata);
                            }
                        location.reload();
                        },
                    }
                    self.plaid_link = Plaid.create(plaid_options);
                    self.plaid_link.open();
                    });
                return this.loaded;
        });

        }


        async make_token(){
            const action = await this.orm.call('online.sync.plaid', 'create_credentials', [this.plaid_client, this.plaid_secret]);
            const link_token = JSON.parse(action);
            this.token_key = link_token.key;
        }

          async linkSuccess(public_token, metadata){
                metadata.environment = this.environment;
                const action = await this.orm.call('online.sync.plaid', 'link_success', [this.id, this.rec_id, public_token, metadata], {context: this.context});
                location.reload();
            }

}
PlaidAccountConfigurationWidget.template = "plaid_sync.plaid_action_view_template";
registry.category("actions").add("plaid_online_sync_widget", PlaidAccountConfigurationWidget);
