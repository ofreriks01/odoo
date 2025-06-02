# Part of Odoo. See LICENSE file for full copyright and licensing details.

from markupsafe import Markup

from odoo import _, fields, models


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    is_donation = fields.Boolean(string="Is donation")
    donation_form_fields = fields.Json(string="Donation form fields")

    def _post_process(self):
        super()._post_process()
        for donation_tx in self.filtered(lambda tx: tx.state == 'done' and tx.is_donation):
            donation_tx._send_donation_email()
            msg = [_('Payment received from donation with following details:')]
            field_names = ['company_id', 'partner_id'] + list(
                (donation_tx.donation_form_fields or {}).keys()
            )

            for key in field_names:
                field = donation_tx._fields.get(key)
                value = donation_tx[key] if field else donation_tx.donation_form_fields.get(key)
                label = field.string if field else key

                if field and field.type == 'many2one' and value:
                    value = value.name
                msg.append(Markup('<br/>- %s: %s') % (label, value))

            donation_tx.payment_id._message_log(body=Markup().join(msg))

    def _send_donation_email(self, is_internal_notification=False, comment=None, recipient_email=None):
        self.ensure_one()
        if is_internal_notification or self.state == 'done':
            subject = _('A donation has been made on your website') if is_internal_notification else _('Donation confirmation')
            body = self.env['ir.qweb'].with_context(lang=self.partner_id.lang)._render('website_payment.donation_mail_body', {
                'is_internal_notification': is_internal_notification,
                'tx': self,
                'comment': comment,
            }, minimal_qcontext=True)
            body = self.env['mail.render.mixin'].with_context(lang=self.partner_id.lang)._render_encapsulate(
                'mail.mail_notification_light',
                body,
                context_record=self,
            )
            self.env['mail.mail'].sudo().create({
                'author_id': self.partner_id.id,
                'body_html': body,
                'email_from': self.company_id.email_formatted,
                'email_to': recipient_email if is_internal_notification else self.partner_email,
                'subject': subject,
            }).send()
