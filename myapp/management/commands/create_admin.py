from django.core.management.base import BaseCommand
from myapp.models import User


class Command(BaseCommand):
    help = 'Creates the default admin user if it does not exist'

    def handle(self, *args, **options):
        admin_email = 'admin@admin.com'
        admin_password = 'Trueadmin123'
        admin_display_name = 'Admin User'

        # Check if admin user already exists
        if User.objects.filter(email=admin_email).exists():
            self.stdout.write(
                self.style.WARNING(f'Admin user with email {admin_email} already exists')
            )
            return

        # Create the admin user
        try:
            admin_user = User.objects.create_superuser(
                email=admin_email,
                password=admin_password,
                display_name=admin_display_name
            )
            # Set the custom role to Admin
            admin_user.role = 1  # Admin role
            admin_user.save()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully created admin user:\n'
                    f'Email: {admin_email}\n'
                    f'Password: {admin_password}\n'
                    f'Display Name: {admin_display_name}'
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating admin user: {str(e)}')
            )
