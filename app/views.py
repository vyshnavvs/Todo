from rest_framework import viewsets, permissions, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Project, Task, TaskDependency # Make sure your models are imported
from .serializers import ProjectSerializer, TaskSerializer, TaskDependencySerializer, TaskListSerializer, LoginSerializer , RegistrationSerializer,TaskAssignmentSerializer# Import LoginSerializer
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.views import APIView # Import APIView
from django.contrib.auth import authenticate, login, logout # Import authentication functions
from django.db import models
from django.core.exceptions import ValidationError
from collections import defaultdict

class RegistrationView(generics.GenericAPIView):
    serializer_class = RegistrationSerializer
    permission_classes = [permissions.AllowAny] # Allow anyone to register

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            user = serializer.save() # Calls serializer's create() method to save the user
            return Response({"detail": "Registration successful. Please log in."}, status=status.HTTP_201_CREATED) # 201 Created for successful registration
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            username = serializer.validated_data['username']
            password = serializer.validated_data['password']
            user = authenticate(request, username=username, password=password) # Django's authenticate function

            if user is not None:
                login(request, user) # Django's login function to establish session
                return Response({"detail": "Login successful."}, status=status.HTTP_200_OK)
            else:
                return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated] # Only logged-in users can logout

    def post(self, request, *args, **kwargs):
        logout(request) # Django's logout function to clear session
        return Response({"detail": "Logout successful."}, status=status.HTTP_200_OK)


class ProjectViewSet(viewsets.ModelViewSet):
    """
    ViewSet for handling Project CRUD operations.
    """
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly] # Public read, authenticated create/update/delete

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user) # Automatically set creator


    def get_queryset(self):
        """
        Customize queryset for listing projects.
        For non-logged-in users, show only project titles and descriptions.
        For logged-in users, show all projects.
        """
        if not self.request.user.is_authenticated:
            return Project.objects.all().only('id', 'title', 'description') # Optimized for public view
        return Project.objects.all()
    
    @action(detail=True, methods=['get'])
    def schedule(self, request, pk=None):
        """
        Action to generate and return an optimal schedule for the project.
        """
        project = self.get_object()
        schedule_data = self.generate_project_schedule(project)
        return Response(schedule_data, status=status.HTTP_200_OK)


    def generate_project_schedule(self, project):
        """
        Generates a project schedule considering task durations, dependencies,
        user constraints (sequential/parallel within project, project switching).
        """
        tasks = list(project.task_set.all()) # Convert QuerySet to list for manipulation
        if not tasks:
            return {"detail": "No tasks in this project to schedule."}

        scheduled_tasks = {} # {task_id: {'start_date': ..., 'end_date': ...}}
        task_start_dates = {} # Track calculated start dates for dependencies
        task_end_dates = {}   # Track calculated end dates for dependencies
        user_last_end_times_in_project = defaultdict(lambda: timezone.datetime.min.replace(tzinfo=timezone.utc)) # Last task end time per user *in this project*
        user_project_workload = defaultdict(set) # Track projects users are currently working on


        # 1. Initial Tasks (no dependencies met initially considered ready to start)
        initial_tasks = [task for task in tasks if task.dependencies_met] # Initially consider all as potentially initial if dependencies are managed dynamically later
        tasks_to_schedule = [task for task in tasks if not task.dependencies_met] # Tasks yet to be scheduled explicitly based on dependency check

        tasks_scheduled_count = 0
        tasks_to_process = initial_tasks[:] # Start with initial tasks


        while tasks_to_process:
            task_to_schedule = tasks_to_process.pop(0) # Process tasks in FIFO order (can be prioritized later)
            if task_to_schedule.id in scheduled_tasks: # Already scheduled, skip
                continue

            user = task_to_schedule.assigned_to
            earliest_start_date = timezone.now().date() # Default start is project start or today - refine if needed

            # Consider sequential task for same user within project:
            last_end_time_user_project = user_last_end_times_in_project[user]
            if last_end_time_user_project > timezone.datetime.min.replace(tzinfo=timezone.utc):
                 earliest_start_date = max(earliest_start_date, last_end_time_user_project.date())


            # Project Switching Constraint:
            if user in user_project_workload: # User has other project workloads
                other_projects = user_project_workload[user]
                if project not in other_projects: # Trying to schedule task in a *new* project
                    currently_working_projects_tasks_incomplete = False
                    for other_proj in other_projects:
                        other_proj_incomplete_tasks_for_user = other_proj.task_set.filter(assigned_to=user, is_completed=False)
                        if other_proj_incomplete_tasks_for_user.exists():
                            currently_working_projects_tasks_incomplete = True
                            break # User still has incomplete tasks in other projects

                    if currently_working_projects_tasks_incomplete:
                        tasks_to_process.append(task_to_schedule) # Defer scheduling, user is busy on other projects
                        continue # To next task in queue


            start_date = earliest_start_date
            end_date = start_date + timezone.timedelta(days=task_to_schedule.duration_days)

            scheduled_tasks[task_to_schedule.id] = {
                'task_id': task_to_schedule.id,
                'title': task_to_schedule.title,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            }
            task_start_dates[task_to_schedule.id] = start_date
            task_end_dates[task_to_schedule.id] = end_date
            user_last_end_times_in_project[user] = max(user_last_end_times_in_project[user], end_date) # Update last end time for user in this project
            user_project_workload[user].add(project) # Track project for user workload management


            tasks_scheduled_count += 1

            # Check for newly schedulable tasks based on dependencies after scheduling current task
            next_schedulable_tasks = []
            for task in tasks_to_schedule:
                 if task.dependencies_met: # Re-evaluate dependencies
                    if task.id not in scheduled_tasks: # And not yet scheduled
                        next_schedulable_tasks.append(task)

            tasks_to_process.extend(next_schedulable_tasks) # Add newly ready tasks to queue
            tasks_to_schedule = [t for t in tasks_to_schedule if t not in next_schedulable_tasks] # Remove added tasks


        return {"schedule": list(scheduled_tasks.values()), "tasks_scheduled_count": tasks_scheduled_count, "total_tasks": len(tasks)}



class TaskViewSet(viewsets.ModelViewSet):
    """
    ViewSet for handling Task CRUD operations.
    """
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated] # Authenticated users only

    def get_queryset(self):
        """
        List tasks for a specific project or all tasks accessible to the user.
        """
        project_id = self.kwargs.get('project_pk') # project_pk from URL conf (nested routes)
        if project_id:
            project = get_object_or_404(Project, pk=project_id)
            return project.tasks.filter(
                models.Q(is_private=False) | models.Q(created_by=self.request.user) | models.Q(assigned_to=self.request.user)
            ) # Show public tasks and tasks created/assigned to the user in the project
        return Task.objects.filter( # If project_pk is not provided, return all tasks accessible to the user across projects (can be customized further)
            models.Q(is_private=False) | models.Q(created_by=self.request.user) | models.Q(assigned_to=self.request.user)
        )

    
    def perform_create(self, serializer):
        project_id = self.kwargs.get('project_pk') # project_pk from URL conf (nested projects case)
        parent_task_id = self.kwargs.get('task_pk') # task_pk from URL conf (nested subtasks case)

        project = None
        parent_task = None

        if project_id: # Creating main task under a project
            project = get_object_or_404(Project, pk=project_id)
        elif parent_task_id: # Creating subtask under a parent task
            parent_task = get_object_or_404(Task, pk=parent_task_id)
            project = parent_task.project # Inherit project from parent task (important for consistency)
        else:
            # Handle error if neither project_pk nor parent_task_pk is provided (if this is an invalid scenario for your app)
            # For now, let's assume task must be under a project or subtask.
            raise ValidationError("Task must be associated with a project or be a subtask of another task.")


        serializer.save(created_by=self.request.user, project=project, parent_task=parent_task) # Set creator, project, and parent_task

    @action(detail=True, methods=['post'])
    def mark_completed(self, request, pk=None):
        """
        Action to mark a task as completed.
        """
        task = self.get_object()
        if task.created_by == request.user or task.assigned_to == request.user:
            if task.is_main_task:
                subtasks_incomplete = task.subtasks.filter(is_completed=False).exists()
                if subtasks_incomplete:
                    return Response({'error': 'Cannot mark main task as complete until all subtasks are completed.'}, status=status.HTTP_400_BAD_REQUEST)

            task.is_completed = True
            task.completion_date = timezone.now()
            task.save()

            if not task.parent_task and not task.is_completed and not task.subtasks.filter(is_completed=False).exists(): # Auto-complete main task
                  task.is_completed = True
                  task.completion_date = timezone.now()
                  task.save()

            return Response({'status': 'Task marked as completed.'})
        else:
            return Response({'error': 'Only creator or assignee can mark task as completed.'}, status=status.HTTP_403_FORBIDDEN)

    @action(detail=True, methods=['get'])
    def subtasks(self, request, pk=None):
        """
        Action to retrieve subtasks for a task.
        """
        task = self.get_object()
        subtasks = task.subtasks.all()
        serializer = TaskSerializer(subtasks, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['patch'], serializer_class=TaskAssignmentSerializer) # New 'assign' action
    def assign(self, request, pk=None):
        """
        Action to assign a task to a user.
        """
        task = self.get_object() # Get the task instance based on pk from URL
        serializer = self.serializer_class(data=request.data) # Use TaskAssignmentSerializer for assignment

        if serializer.is_valid():
            assigned_to_user = serializer.validated_data['assigned_to_id'] # Get the user from validated data

            # Authorization Check (Optional but recommended):
            # For now, let's just assume creator or project members can assign.
            # You might need more specific permission logic based on requirements.
            if task.created_by == request.user or task.project.created_by == request.user : # Example: Creator or project creator can assign
                task.assigned_to = assigned_to_user # Assign the task
                task.save()
                task_serializer = TaskSerializer(task) # Serialize the updated task (using full TaskSerializer to return all task details)
                return Response(task_serializer.data, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'You do not have permission to assign this task.'}, status=status.HTTP_403_FORBIDDEN)

        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class TaskDependencyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for handling TaskDependency CRUD operations.
    """
    serializer_class = TaskDependencySerializer
    permission_classes = [permissions.IsAuthenticated] # Authenticated users only

    def get_queryset(self):
        """
        List dependencies for a specific task.
        """
        task_id = self.kwargs.get('task_pk') # task_pk from URL conf (nested routes)
        if task_id:
            task = get_object_or_404(Task, pk=task_id)
            return task.dependencies.all()
        return TaskDependency.objects.all() # Or customize to show user's dependencies across projects

    def perform_create(self, serializer):
        task_id = self.kwargs['task_pk'] # task_pk from URL conf
        task = get_object_or_404(Task, pk=task_id)
        serializer.save(task=task) # Set the task for the dependency


class AssignedTaskListView(generics.ListAPIView):
    """
    API View to list tasks assigned to the logged-in user.
    """
    serializer_class = TaskListSerializer # Using TaskListSerializer to include assigned user details
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Return tasks assigned to the current user.
        """
        return Task.objects.filter(assigned_to=self.request.user)