from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = 'Detect users whose password field looks like a plain (not hashed) value and re-hash it using set_password()'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show which users would be changed without modifying the database')
        parser.add_argument('--limit', type=int, default=0, help='Limit number of users to process (0 = all)')

    def handle(self, *args, **options):
        User = get_user_model()
        dry_run = options['dry_run']
        limit = options['limit']
        
        known_prefixes = ('pbkdf2_', 'argon2', 'bcrypt', 'bcrypt_sha256', 'sha1$', 'md5$')

        qs = User.objects.all()
        changed = 0
        checked = 0

        for user in qs:
            pw = (user.password or '')
            checked += 1

            is_hashed = False
            if '$' in pw:
                prefix = pw.split('$', 1)[0]
                for alg in known_prefixes:
                    if prefix.startswith(alg):
                        is_hashed = True
                        break

            if not is_hashed:
                self.stdout.write(self.style.WARNING(f'User {user.pk} ({user.email}) appears to have a non-hashed password: "{pw[:30]}..."'))
                if dry_run:
                    continue
                raw = pw
                try:
                    user.set_password(raw)
                    user.save()
                    changed += 1
                    self.stdout.write(self.style.SUCCESS(f'  Re-hashed password for user {user.pk} ({user.email})'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  Failed to re-hash for user {user.pk}: {e}'))

            if limit and changed >= limit:
                break

        self.stdout.write(f'Checked {checked} users; re-hashed {changed} users (dry-run={dry_run}).')
