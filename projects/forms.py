from django import forms
from django.contrib.auth.models import User
from .models import Project, ProjectMember, Task, Comment


class ProjectForm(forms.ModelForm):
    deadline = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    class Meta:
        model = Project
        fields = ['title', 'description', 'status', 'deadline']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter project title (e.g., Mobile App Redesign)'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe project goals, scope, and objectives...'
            }),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }


class ProjectMemberForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label='Select a user to add'
    )
    role = forms.ChoiceField(
        choices=ProjectMember.ROLE_CHOICES,
        initial='Member',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        if project:
            # Exclude users who are already members or creator
            existing_member_ids = project.memberships.values_list('user_id', flat=True)
            self.fields['user'].queryset = User.objects.exclude(
                id__in=list(existing_member_ids) + [project.created_by.id]
            ).order_by('username')


class TaskForm(forms.ModelForm):
    due_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    class Meta:
        model = Task
        fields = ['title', 'description', 'assigned_to', 'priority', 'status', 'due_date']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter task title (e.g. Design wireframes)'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Provide task instructions, requirements, or acceptance criteria...'
            }),
            'assigned_to': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        if project:
            # Limit assignable users to project members plus the creator
            member_ids = list(project.memberships.values_list('user_id', flat=True))
            member_ids.append(project.created_by.id)
            self.fields['assigned_to'].queryset = User.objects.filter(id__in=member_ids).order_by('username')
        else:
            self.fields['assigned_to'].queryset = User.objects.all().order_by('username')
        self.fields['assigned_to'].empty_label = 'Unassigned'


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Write a comment or update on this task...'
            })
        }
