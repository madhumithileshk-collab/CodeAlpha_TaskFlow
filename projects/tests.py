from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from projects.models import Project, ProjectMember, Task, Comment, Notification, create_notification
from datetime import date, timedelta


class TaskFlowEndToEndTests(TestCase):
    def setUp(self):
        self.client = Client()
        # Create users
        self.user1 = User.objects.create_user(username='alice', password='Password123!', email='alice@example.com', first_name='Alice', last_name='Smith')
        self.user2 = User.objects.create_user(username='bob', password='Password123!', email='bob@example.com', first_name='Bob', last_name='Jones')

    def test_user_profile_signal(self):
        """Test that user profile is automatically created via post_save signal."""
        self.assertTrue(hasattr(self.user1, 'profile'))
        self.assertEqual(self.user1.profile.get_initials(), 'AS')

    def test_authentication_flow(self):
        """Test login, dashboard access, and logout."""
        # Unauthenticated dashboard redirects to login
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)

        # Login
        login_success = self.client.login(username='alice', password='Password123!')
        self.assertTrue(login_success)

        # Dashboard accessible
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alice')

    def test_project_crud(self):
        """Test creating, viewing, and editing projects."""
        self.client.login(username='alice', password='Password123!')

        # Create project
        response = self.client.post(reverse('project_create'), {
            'title': 'TaskFlow Platform',
            'description': 'Building next-gen project management tool',
            'status': 'in_progress',
            'deadline': date.today() + timedelta(days=14)
        })
        self.assertEqual(response.status_code, 302)
        project = Project.objects.filter(title='TaskFlow Platform').first()
        self.assertIsNotNone(project)
        self.assertEqual(project.created_by, self.user1)

        # Creator automatically added as owner
        self.assertTrue(project.is_member(self.user1))
        self.assertTrue(project.can_manage(self.user1))

        # View project detail
        response = self.client.get(reverse('project_detail', args=[project.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'TaskFlow Platform')

        # Add bob as member
        response = self.client.post(reverse('project_add_member', args=[project.pk]), {
            'user': self.user2.id,
            'role': 'Member'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(project.is_member(self.user2))

        # Check notification sent to bob
        notif = Notification.objects.filter(recipient=self.user2).first()
        self.assertIsNotNone(notif)
        self.assertIn('added you to project', notif.message)

    def test_task_management_and_comments(self):
        """Test creating tasks, changing statuses, adding comments, and notifications."""
        project = Project.objects.create(
            title='Mobile App',
            description='React Native App',
            created_by=self.user1
        )
        ProjectMember.objects.create(project=project, user=self.user1, role='Owner')
        ProjectMember.objects.create(project=project, user=self.user2, role='Member')

        self.client.login(username='alice', password='Password123!')

        # Create task assigned to Bob
        response = self.client.post(reverse('task_create', args=[project.pk]), {
            'title': 'Setup Navigation',
            'description': 'Configure React Navigation stack',
            'assigned_to': self.user2.id,
            'priority': 'High',
            'status': 'To Do',
            'due_date': date.today() + timedelta(days=5)
        })
        self.assertEqual(response.status_code, 302)

        task = Task.objects.filter(title='Setup Navigation').first()
        self.assertIsNotNone(task)
        self.assertEqual(task.assigned_to, self.user2)
        self.assertEqual(task.priority, 'High')

        # Verify Bob received task assignment notification
        assignment_notif = Notification.objects.filter(recipient=self.user2, notification_type='task_assigned').first()
        self.assertIsNotNone(assignment_notif)
        self.assertIn('assigned you task', assignment_notif.message)

        # Quick status transition
        response = self.client.post(reverse('task_quick_status', args=[task.pk]), {
            'status': 'In Progress'
        })
        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.status, 'In Progress')

        # Bob logs in and comments on the task
        self.client.login(username='bob', password='Password123!')
        response = self.client.post(reverse('task_add_comment', args=[task.pk]), {
            'content': 'I have started implementing the authentication stack.'
        })
        self.assertEqual(response.status_code, 302)

        self.assertEqual(task.comments.count(), 1)
        comment = task.comments.first()
        self.assertEqual(comment.author, self.user2)

        # Alice should have received comment notification
        comment_notif = Notification.objects.filter(recipient=self.user1, notification_type='comment').first()
        self.assertIsNotNone(comment_notif)
        self.assertIn('commented on task', comment_notif.message)

    def test_search_and_filters(self):
        """Test search and filter capabilities for tasks and projects."""
        project = Project.objects.create(title='Backend API', created_by=self.user1, status='in_progress')
        ProjectMember.objects.create(project=project, user=self.user1, role='Owner')

        t1 = Task.objects.create(project=project, title='User Auth API', priority='High', status='To Do', created_by=self.user1)
        t2 = Task.objects.create(project=project, title='Payment Webhook', priority='Low', status='Completed', created_by=self.user1)

        self.client.login(username='alice', password='Password123!')

        # Filter tasks by status
        response = self.client.get(reverse('task_list') + '?status=To+Do')
        self.assertContains(response, 'User Auth API')
        self.assertNotContains(response, 'Payment Webhook')

        # Filter tasks by priority
        response = self.client.get(reverse('task_list') + '?priority=High')
        self.assertContains(response, 'User Auth API')
        self.assertNotContains(response, 'Payment Webhook')

        # Search tasks
        response = self.client.get(reverse('task_list') + '?q=Payment')
        self.assertContains(response, 'Payment Webhook')
        self.assertNotContains(response, 'User Auth API')
