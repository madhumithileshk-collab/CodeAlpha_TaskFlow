from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from projects.models import Project, ProjectMember, Task, Comment, Notification
from datetime import date, timedelta


class Command(BaseCommand):
    help = 'Seeds the TaskFlow database with realistic sample projects, tasks, comments, and users.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Seeding TaskFlow demo data...'))

        # 1. Create Superuser / Admin
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@taskflow.dev',
                'first_name': 'TaskFlow',
                'last_name': 'Administrator',
                'is_staff': True,
                'is_superuser': True
            }
        )
        if created:
            admin_user.set_password('admin123')
            admin_user.save()
            admin_user.profile.role_title = 'Lead Architect & Admin'
            admin_user.profile.save()
            self.stdout.write(self.style.SUCCESS('Created admin user: admin / admin123'))
        else:
            self.stdout.write('Admin user already exists.')

        # 2. Create Team Members
        users_data = [
            ('sarah_dev', 'Sarah', 'Connor', 'sarah@taskflow.dev', 'Senior Frontend Engineer'),
            ('alex_pm', 'Alex', 'Rivera', 'alex@taskflow.dev', 'Senior Project Manager'),
            ('david_backend', 'David', 'Kim', 'david@taskflow.dev', 'Backend & Cloud Engineer'),
        ]

        team = {}
        for username, first, last, email, role in users_data:
            u, cr = User.objects.get_or_create(
                username=username,
                defaults={'first_name': first, 'last_name': last, 'email': email}
            )
            if cr:
                u.set_password('demo1234')
                u.save()
                u.profile.role_title = role
                u.profile.save()
            team[username] = u

        # 3. Create Sample Projects
        p1, cr = Project.objects.get_or_create(
            title='TaskFlow Cloud Platform',
            created_by=admin_user,
            defaults={
                'description': 'Architecting the scalable web portal, real-time collaboration widgets, and database indexing.',
                'status': 'in_progress',
                'deadline': date.today() + timedelta(days=20),
            }
        )
        if cr:
            ProjectMember.objects.get_or_create(project=p1, user=admin_user, defaults={'role': 'Owner'})
            ProjectMember.objects.get_or_create(project=p1, user=team['sarah_dev'], defaults={'role': 'Member'})
            ProjectMember.objects.get_or_create(project=p1, user=team['david_backend'], defaults={'role': 'Admin'})

        p2, cr = Project.objects.get_or_create(
            title='Mobile Companion Application',
            created_by=team['alex_pm'],
            defaults={
                'description': 'Cross-platform mobile app enabling notifications, fast sprint tracking, and offline sync.',
                'status': 'planning',
                'deadline': date.today() + timedelta(days=45),
            }
        )
        if cr:
            ProjectMember.objects.get_or_create(project=p2, user=team['alex_pm'], defaults={'role': 'Owner'})
            ProjectMember.objects.get_or_create(project=p2, user=admin_user, defaults={'role': 'Admin'})
            ProjectMember.objects.get_or_create(project=p2, user=team['sarah_dev'], defaults={'role': 'Member'})

        # 4. Create Sample Tasks for Project 1
        t1, cr = Task.objects.get_or_create(
            project=p1,
            title='Design Modern Dashboard UI & Analytics Cards',
            created_by=admin_user,
            defaults={
                'description': 'Implement responsive cards for total projects, completed tasks, and progress indicators using Bootstrap 5.',
                'assigned_to': team['sarah_dev'],
                'priority': 'High',
                'status': 'Completed',
                'due_date': date.today() - timedelta(days=1),
            }
        )

        t2, cr = Task.objects.get_or_create(
            project=p1,
            title='Implement In-App Notification System',
            created_by=admin_user,
            defaults={
                'description': 'Deliver instant notifications on task assignment, comments, and status transitions.',
                'assigned_to': team['david_backend'],
                'priority': 'High',
                'status': 'In Progress',
                'due_date': date.today() + timedelta(days=3),
            }
        )

        t3, cr = Task.objects.get_or_create(
            project=p1,
            title='Optimize SQLite Database Queries & Admin Filters',
            created_by=admin_user,
            defaults={
                'description': 'Add indexes, foreign key cascading, search filters, and tabular inlines to Django Admin.',
                'assigned_to': admin_user,
                'priority': 'Medium',
                'status': 'To Do',
                'due_date': date.today() + timedelta(days=7),
            }
        )

        # 5. Create Comments
        if not Comment.objects.filter(task=t2).exists():
            c1 = Comment.objects.create(
                task=t2,
                author=team['david_backend'],
                content='Notification context processor and bell dropdown icon are linked successfully.'
            )
            c2 = Comment.objects.create(
                task=t2,
                author=admin_user,
                content='Awesome! Please ensure unread counters decrement properly upon opening.'
            )

        # 6. Create Notifications
        Notification.objects.get_or_create(
            recipient=admin_user,
            sender=team['david_backend'],
            message='david_backend commented on task "Implement In-App Notification System".',
            task=t2,
            project=p1,
            defaults={'notification_type': 'comment', 'is_read': False}
        )

        Notification.objects.get_or_create(
            recipient=team['sarah_dev'],
            sender=admin_user,
            message='admin assigned you task "Design Modern Dashboard UI & Analytics Cards" in "TaskFlow Cloud Platform".',
            task=t1,
            project=p1,
            defaults={'notification_type': 'task_assigned', 'is_read': True}
        )

        self.stdout.write(self.style.SUCCESS('Successfully seeded TaskFlow database!'))
