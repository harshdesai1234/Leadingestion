"""
Management command to test the email configuration.

Usage:
    python manage.py test_email --to your@email.com

Prints current settings, tries an SMTP connection, and sends a test email.
"""
import smtplib
import ssl

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Test the email configuration by sending a test email."

    def add_arguments(self, parser):
        parser.add_argument(
            '--to',
            type=str,
            required=True,
            help='Recipient email address for the test email.',
        )

    def handle(self, *args, **options):
        recipient = options['to']

        # ── 1. Print current config ───────────────────────────────────────────
        self.stdout.write(self.style.HTTP_INFO("\n── Email Configuration ──────────────────────────────"))
        self.stdout.write(f"  BACKEND  : {settings.EMAIL_BACKEND}")
        self.stdout.write(f"  HOST     : {settings.EMAIL_HOST}")
        self.stdout.write(f"  PORT     : {settings.EMAIL_PORT}")
        self.stdout.write(f"  USE_SSL  : {getattr(settings, 'EMAIL_USE_SSL', False)}")
        self.stdout.write(f"  USE_TLS  : {settings.EMAIL_USE_TLS}")
        self.stdout.write(f"  USER     : {settings.EMAIL_HOST_USER or '(empty)'}")
        self.stdout.write(f"  PASSWORD : {'(set)' if settings.EMAIL_HOST_PASSWORD else '(empty)'}")
        self.stdout.write(f"  FROM     : {settings.DEFAULT_FROM_EMAIL}")
        self.stdout.write(f"  TO       : {recipient}")
        self.stdout.write("")

        if 'console' in settings.EMAIL_BACKEND.lower():
            self.stdout.write(self.style.WARNING(
                "⚠  Console backend is active — emails print to terminal only.\n"
                "   Set EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend in .env"
            ))
            return

        # ── 2. Test raw SMTP connection first ─────────────────────────────────
        self.stdout.write(self.style.HTTP_INFO("── Testing raw SMTP connection ──────────────────────"))
        use_ssl = getattr(settings, 'EMAIL_USE_SSL', False)
        host    = settings.EMAIL_HOST
        port    = settings.EMAIL_PORT
        user    = settings.EMAIL_HOST_USER
        pw      = settings.EMAIL_HOST_PASSWORD

        try:
            if use_ssl:
                ctx    = ssl.create_default_context()
                server = smtplib.SMTP_SSL(host, port, context=ctx, timeout=10)
            else:
                server = smtplib.SMTP(host, port, timeout=10)
                if settings.EMAIL_USE_TLS:
                    ctx = ssl.create_default_context()
                    server.starttls(context=ctx)

            self.stdout.write(f"  Connected to {host}:{port}  ✓")

            if user:
                server.login(user, pw)
                self.stdout.write(f"  Authenticated as {user}  ✓")

            server.quit()
            self.stdout.write(self.style.SUCCESS("  Raw SMTP test passed ✓"))

        except smtplib.SMTPAuthenticationError as e:
            self.stdout.write(self.style.ERROR(f"  Auth failed: {e}"))
            self.stdout.write(self.style.ERROR(
                "  → Check EMAIL_HOST_USER and EMAIL_HOST_PASSWORD in .env\n"
                "  → For AWS SES, make sure you are using SMTP credentials\n"
                "    (not IAM access keys directly — they must be converted via\n"
                "     aws iam create-smtp-credential or the SES console)"
            ))
            return

        except smtplib.SMTPConnectError as e:
            self.stdout.write(self.style.ERROR(f"  Connection refused: {e}"))
            self.stdout.write(self.style.ERROR(
                f"  → Cannot reach {host}:{port}\n"
                f"  → Check EMAIL_HOST, EMAIL_PORT, EMAIL_USE_SSL"
            ))
            return

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  SMTP error: {type(e).__name__}: {e}"))
            return

        # ── 3. Send via Django's send_mail ────────────────────────────────────
        self.stdout.write(self.style.HTTP_INFO("\n── Sending test email via Django ────────────────────"))
        try:
            send_mail(
                subject="[Agentyne] Email test",
                message=(
                    "This is a test email from Agentyne.\n\n"
                    "If you received this, your email configuration is working correctly."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                fail_silently=False,
            )
            self.stdout.write(self.style.SUCCESS(
                f"  Email sent to {recipient}  ✓\n"
                f"  Check your inbox (and spam folder)."
            ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  send_mail failed: {type(e).__name__}: {e}"))
            self.stdout.write(self.style.ERROR(
                "  → If the error mentions 'sender not verified', the FROM address\n"
                f"    ({settings.DEFAULT_FROM_EMAIL}) is not verified in AWS SES.\n"
                "  → If SES is in sandbox mode, the recipient must also be verified."
            ))
