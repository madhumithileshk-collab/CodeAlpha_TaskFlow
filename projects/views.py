from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count
from django.http import HttpResponseForbidden, JsonResponse
from django.contrib.auth.models import User
from .models import Project, ProjectMember, Task, Comment, Notification, create_notification
from .forms import ProjectForm, ProjectMemberForm, TaskForm, CommentForm


def home_view(request):
    """Landing page for TaskFlow."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'home.html')


@login_required
def dashboard_view(request):
    """Main dashboard displaying projects, tasks, statistics, and notifications."""
    user = request.user
    
    # Projects the user created or is a member of
    user_projects = Project.objects.filter(
        Q(created_by=user) | Q(memberships__user=user)
    ).distinct()

    # Tasks within user's projects
    user_tasks = Task.objects.filter(project__in=user_projects).distinct()

    # Metrics
    total_projects = user_projects.count()
    total_tasks = user_tasks.count()
    completed_tasks = user_tasks.filter(status='Completed').count()
    in_progress_tasks = user_tasks.filter(status='In Progress').count()
    todo_tasks = user_tasks.filter(status='To Do').count()
    pending_tasks = total_tasks - completed_tasks

    # Specific to current user
    my_assigned_tasks = Task.objects.filter(assigned_to=user).distinct()
    my_pending_tasks = my_assigned_tasks.exclude(status='Completed').count()
    high_priority_tasks = user_tasks.filter(priority='High').exclude(status='Completed').count()

    completion_rate = int((completed_tasks / total_tasks * 100)) if total_tasks > 0 else 0

    # Recent items
    recent_projects = user_projects.order_by('-created_at')[:4]
    recent_tasks = user_tasks.select_related('project', 'assigned_to').order_by('-created_at')[:6]
    my_tasks_list = my_assigned_tasks.select_related('project').exclude(status='Completed').order_by('due_date', '-created_at')[:5]

    # Recent notifications
    recent_notifications = Notification.objects.filter(
        recipient=user
    ).select_related('sender', 'task', 'project').order_by('-created_at')[:5]

    context = {
        'total_projects': total_projects,
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'in_progress_tasks': in_progress_tasks,
        'todo_tasks': todo_tasks,
        'pending_tasks': pending_tasks,
        'my_pending_tasks': my_pending_tasks,
        'high_priority_tasks': high_priority_tasks,
        'completion_rate': completion_rate,
        'recent_projects': recent_projects,
        'recent_tasks': recent_tasks,
        'my_tasks_list': my_tasks_list,
        'recent_notifications': recent_notifications,
    }
    return render(request, 'dashboard.html', context)


# ==========================================
# PROJECT VIEWS
# ==========================================

@login_required
def project_list(request):
    """View all projects accessible to the user with search and status filter."""
    user = request.user
    projects = Project.objects.filter(
        Q(created_by=user) | Q(memberships__user=user)
    ).distinct()

    # Search query
    q = request.GET.get('q', '').strip()
    if q:
        projects = projects.filter(
            Q(title__icontains=q) | Q(description__icontains=q)
        )

    # Status filter
    status = request.GET.get('status', '').strip()
    if status:
        projects = projects.filter(status=status)

    context = {
        'projects': projects,
        'q': q,
        'selected_status': status,
        'total_count': projects.count(),
    }
    return render(request, 'projects/project_list.html', context)


@login_required
def project_detail(request, pk):
    """View project details, tasks, and member list."""
    user = request.user
    project = get_object_or_404(Project, pk=pk)

    if not project.is_member(user) and not user.is_superuser:
        messages.error(request, 'You do not have permission to access this project.')
        return redirect('project_list')

    tasks = project.tasks.select_related('assigned_to', 'created_by').all()

    # Task filtering within project
    task_status = request.GET.get('status', '').strip()
    task_priority = request.GET.get('priority', '').strip()
    task_q = request.GET.get('tq', '').strip()

    if task_status:
        tasks = tasks.filter(status=task_status)
    if task_priority:
        tasks = tasks.filter(priority=task_priority)
    if task_q:
        tasks = tasks.filter(
            Q(title__icontains=task_q) | Q(description__icontains=task_q)
        )

    # Members list
    memberships = project.memberships.select_related('user', 'user__profile').all()
    can_manage = project.can_manage(user)
    member_form = ProjectMemberForm(project=project) if can_manage else None

    # Grouped tasks for kanban / board view
    todo_tasks = project.tasks.filter(status='To Do').select_related('assigned_to')
    in_progress_tasks = project.tasks.filter(status='In Progress').select_related('assigned_to')
    completed_tasks = project.tasks.filter(status='Completed').select_related('assigned_to')

    context = {
        'project': project,
        'tasks': tasks,
        'todo_tasks': todo_tasks,
        'in_progress_tasks': in_progress_tasks,
        'completed_tasks': completed_tasks,
        'memberships': memberships,
        'can_manage': can_manage,
        'member_form': member_form,
        'task_status': task_status,
        'task_priority': task_priority,
        'task_q': task_q,
    }
    return render(request, 'projects/project_detail.html', context)


@login_required
def project_create(request):
    """Create a new project."""
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.created_by = request.user
            project.save()

            # Automatically add creator as Owner in ProjectMember
            ProjectMember.objects.create(
                project=project,
                user=request.user,
                role='Owner'
            )

            messages.success(request, f'Project "{project.title}" created successfully!')
            return redirect('project_detail', pk=project.pk)
        else:
            messages.error(request, 'Please correct the errors in the project form.')
    else:
        form = ProjectForm()

    return render(request, 'projects/project_form.html', {'form': form, 'title': 'Create New Project', 'btn_text': 'Create Project'})


@login_required
def project_edit(request, pk):
    """Edit an existing project."""
    project = get_object_or_404(Project, pk=pk)

    if not project.can_manage(request.user):
        messages.error(request, 'You do not have permission to edit this project.')
        return redirect('project_detail', pk=project.pk)

    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, f'Project "{project.title}" updated successfully!')
            return redirect('project_detail', pk=project.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ProjectForm(instance=project)

    return render(request, 'projects/project_form.html', {
        'form': form,
        'project': project,
        'title': f'Edit Project: {project.title}',
        'btn_text': 'Save Changes'
    })


@login_required
def project_delete(request, pk):
    """Delete a project (creator or superuser only)."""
    project = get_object_or_404(Project, pk=pk)

    if project.created_by != request.user and not request.user.is_superuser:
        messages.error(request, 'Only the project creator can delete this project.')
        return redirect('project_detail', pk=project.pk)

    if request.method == 'POST':
        project_title = project.title
        project.delete()
        messages.success(request, f'Project "{project_title}" has been deleted.')
        return redirect('project_list')

    return render(request, 'projects/project_confirm_delete.html', {'project': project})


@login_required
def project_add_member(request, pk):
    """Add a member to the project."""
    project = get_object_or_404(Project, pk=pk)

    if not project.can_manage(request.user):
        messages.error(request, 'You do not have permission to add members to this project.')
        return redirect('project_detail', pk=project.pk)

    if request.method == 'POST':
        form = ProjectMemberForm(request.POST, project=project)
        if form.is_valid():
            new_user = form.cleaned_data['user']
            role = form.cleaned_data['role']
            membership, created = ProjectMember.objects.get_or_create(
                project=project,
                user=new_user,
                defaults={'role': role}
            )
            if created:
                messages.success(request, f'{new_user.username} has been added to {project.title} as {role}.')
                create_notification(
                    recipient=new_user,
                    sender=request.user,
                    message=f'{request.user.username} added you to project "{project.title}" as {role}.',
                    project=project,
                    notification_type='member_added'
                )
            else:
                membership.role = role
                membership.save()
                messages.info(request, f'Updated {new_user.username}\'s role to {role}.')
        else:
            messages.error(request, 'Could not add member. Please verify the selected user.')

    return redirect('project_detail', pk=project.pk)


@login_required
def project_remove_member(request, pk, user_id):
    """Remove a member from the project."""
    project = get_object_or_404(Project, pk=pk)

    if not project.can_manage(request.user):
        messages.error(request, 'You do not have permission to manage team members.')
        return redirect('project_detail', pk=project.pk)

    target_user = get_object_or_404(User, pk=user_id)
    if target_user == project.created_by:
        messages.error(request, 'The project owner cannot be removed.')
        return redirect('project_detail', pk=project.pk)

    membership = ProjectMember.objects.filter(project=project, user=target_user).first()
    if membership:
        membership.delete()
        # Unassign tasks in this project from removed user
        project.tasks.filter(assigned_to=target_user).update(assigned_to=None)
        messages.success(request, f'{target_user.username} was removed from the project.')

    return redirect('project_detail', pk=project.pk)


# ==========================================
# TASK VIEWS
# ==========================================

@login_required
def task_list(request):
    """View all tasks accessible to user with search and filtering."""
    user = request.user
    user_projects = Project.objects.filter(
        Q(created_by=user) | Q(memberships__user=user)
    ).distinct()

    tasks = Task.objects.filter(project__in=user_projects).select_related('project', 'assigned_to').distinct()

    # Search
    q = request.GET.get('q', '').strip()
    if q:
        tasks = tasks.filter(
            Q(title__icontains=q) | Q(description__icontains=q) | Q(project__title__icontains=q)
        )

    # Status filter
    status = request.GET.get('status', '').strip()
    if status:
        tasks = tasks.filter(status=status)

    # Priority filter
    priority = request.GET.get('priority', '').strip()
    if priority:
        tasks = tasks.filter(priority=priority)

    # Project filter
    project_id = request.GET.get('project', '').strip()
    if project_id:
        tasks = tasks.filter(project_id=project_id)

    # Assigned to me filter
    assigned_filter = request.GET.get('assigned', '').strip()
    if assigned_filter == 'me':
        tasks = tasks.filter(assigned_to=user)

    context = {
        'tasks': tasks,
        'projects': user_projects,
        'q': q,
        'selected_status': status,
        'selected_priority': priority,
        'selected_project': project_id,
        'assigned_filter': assigned_filter,
        'total_count': tasks.count(),
    }
    return render(request, 'projects/task_list.html', context)


@login_required
def task_create(request, project_id):
    """Create a task inside a specific project."""
    project = get_object_or_404(Project, pk=project_id)

    if not project.is_member(request.user) and not request.user.is_superuser:
        messages.error(request, 'You do not have permission to add tasks to this project.')
        return redirect('project_list')

    if request.method == 'POST':
        form = TaskForm(request.POST, project=project)
        if form.is_valid():
            task = form.save(commit=False)
            task.project = project
            task.created_by = request.user
            task.save()

            # In-app notification when task is assigned to a user
            if task.assigned_to and task.assigned_to != request.user:
                create_notification(
                    recipient=task.assigned_to,
                    sender=request.user,
                    message=f'{request.user.username} assigned you task "{task.title}" in "{project.title}".',
                    task=task,
                    project=project,
                    notification_type='task_assigned'
                )

            messages.success(request, f'Task "{task.title}" created successfully!')
            return redirect('task_detail', pk=task.pk)
        else:
            messages.error(request, 'Please check the form inputs.')
    else:
        form = TaskForm(project=project)

    return render(request, 'projects/task_form.html', {
        'form': form,
        'project': project,
        'title': f'Create Task in {project.title}',
        'btn_text': 'Create Task'
    })


@login_required
def task_detail(request, pk):
    """View task details and comments."""
    task = get_object_or_404(Task.objects.select_related('project', 'assigned_to', 'created_by'), pk=pk)

    if not task.project.is_member(request.user) and not request.user.is_superuser:
        messages.error(request, 'You do not have access to this task.')
        return redirect('task_list')

    comments = task.comments.select_related('author', 'author__profile').all()
    comment_form = CommentForm()

    context = {
        'task': task,
        'comments': comments,
        'comment_form': comment_form,
    }
    return render(request, 'projects/task_detail.html', context)


@login_required
def task_edit(request, pk):
    """Edit task details."""
    task = get_object_or_404(Task.objects.select_related('project'), pk=pk)

    if not task.project.is_member(request.user) and not request.user.is_superuser:
        messages.error(request, 'You do not have permission to edit this task.')
        return redirect('task_list')

    previous_assignee = task.assigned_to

    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task, project=task.project)
        if form.is_valid():
            updated_task = form.save()

            # Notify new assignee if changed
            if updated_task.assigned_to and updated_task.assigned_to != previous_assignee and updated_task.assigned_to != request.user:
                create_notification(
                    recipient=updated_task.assigned_to,
                    sender=request.user,
                    message=f'{request.user.username} assigned you task "{updated_task.title}" in "{updated_task.project.title}".',
                    task=updated_task,
                    project=updated_task.project,
                    notification_type='task_assigned'
                )

            messages.success(request, f'Task "{updated_task.title}" updated successfully!')
            return redirect('task_detail', pk=task.pk)
        else:
            messages.error(request, 'Please correct the errors in the task form.')
    else:
        form = TaskForm(instance=task, project=task.project)

    return render(request, 'projects/task_form.html', {
        'form': form,
        'project': task.project,
        'task': task,
        'title': f'Edit Task: {task.title}',
        'btn_text': 'Update Task'
    })


@login_required
def task_delete(request, pk):
    """Delete a task."""
    task = get_object_or_404(Task, pk=pk)
    project = task.project

    if not (project.can_manage(request.user) or task.created_by == request.user or request.user.is_superuser):
        messages.error(request, 'You do not have permission to delete this task.')
        return redirect('task_detail', pk=task.pk)

    if request.method == 'POST':
        title = task.title
        task.delete()
        messages.success(request, f'Task "{title}" has been deleted.')
        return redirect('project_detail', pk=project.pk)

    return render(request, 'projects/task_confirm_delete.html', {'task': task, 'project': project})


@login_required
def task_quick_status(request, pk):
    """Quickly update a task's status from anywhere (e.g. board/dashboard/detail)."""
    task = get_object_or_404(Task, pk=pk)

    if not task.project.is_member(request.user) and not request.user.is_superuser:
        messages.error(request, 'Permission denied.')
        return redirect('task_list')

    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(Task.STATUS_CHOICES):
            task.status = new_status
            task.save()
            messages.success(request, f'Task "{task.title}" status updated to {new_status}.')

            # Notify assignee or creator if another user updated the status
            notify_target = task.assigned_to if task.assigned_to != request.user else task.created_by
            if notify_target and notify_target != request.user:
                create_notification(
                    recipient=notify_target,
                    sender=request.user,
                    message=f'{request.user.username} updated status of "{task.title}" to "{new_status}".',
                    task=task,
                    project=task.project,
                    notification_type='status_update'
                )

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'task_detail'
    if next_url == 'task_detail':
        return redirect('task_detail', pk=task.pk)
    return redirect(next_url)


# ==========================================
# COMMENT VIEWS
# ==========================================

@login_required
def task_add_comment(request, pk):
    """Add a comment to a task."""
    task = get_object_or_404(Task, pk=pk)

    if not task.project.is_member(request.user) and not request.user.is_superuser:
        messages.error(request, 'Permission denied.')
        return redirect('task_list')

    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.task = task
            comment.author = request.user
            comment.save()

            # Notify assigned user or creator about new comment
            targets = set()
            if task.assigned_to:
                targets.add(task.assigned_to)
            if task.created_by:
                targets.add(task.created_by)
            targets.discard(request.user)

            for target in targets:
                create_notification(
                    recipient=target,
                    sender=request.user,
                    message=f'{request.user.username} commented on task "{task.title}".',
                    task=task,
                    project=task.project,
                    notification_type='comment'
                )

            messages.success(request, 'Your comment has been added.')
        else:
            messages.error(request, 'Comment content cannot be empty.')

    return redirect('task_detail', pk=task.pk)


@login_required
def comment_delete(request, pk):
    """Delete a comment (author or admin only)."""
    comment = get_object_or_404(Comment, pk=pk)
    task_pk = comment.task.pk

    if comment.author == request.user or comment.task.project.can_manage(request.user) or request.user.is_superuser:
        comment.delete()
        messages.success(request, 'Comment deleted.')
    else:
        messages.error(request, 'You cannot delete this comment.')

    return redirect('task_detail', pk=task_pk)


# ==========================================
# NOTIFICATION VIEWS
# ==========================================

@login_required
def notification_list(request):
    """View all notifications for the logged-in user."""
    notifications = Notification.objects.filter(
        recipient=request.user
    ).select_related('sender', 'task', 'project').order_by('-created_at')

    unread_count = notifications.filter(is_read=False).count()

    context = {
        'notifications': notifications,
        'unread_count': unread_count,
    }
    return render(request, 'projects/notification_list.html', context)


@login_required
def mark_notification_read(request, pk):
    """Mark a notification as read and optionally navigate to the related task/project."""
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.is_read = True
    notification.save()

    if notification.task:
        return redirect('task_detail', pk=notification.task.pk)
    elif notification.project:
        return redirect('project_detail', pk=notification.project.pk)
    return redirect('notification_list')


@login_required
def mark_all_notifications_read(request):
    """Mark all notifications for the user as read."""
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    messages.success(request, 'All notifications marked as read.')
    return redirect('notification_list')
