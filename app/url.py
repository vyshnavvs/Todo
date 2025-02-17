from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProjectViewSet, TaskViewSet, TaskDependencyViewSet, AssignedTaskListView,LoginView,LogoutView,RegistrationView

router = DefaultRouter()
router.register(r'projects', ProjectViewSet, basename='project')
router.register(r'tasks', TaskViewSet, basename='task') # For general task operations, if needed outside project context
router.register(r'task-dependencies', TaskDependencyViewSet, basename='taskdependency') # For general dependency operations, if needed

# Nested routers for project-specific tasks and task-specific dependencies
project_router = DefaultRouter()
project_router.register(r'tasks', TaskViewSet, basename='project-tasks') # Tasks under projects

task_router = DefaultRouter()
task_router.register(r'dependencies', TaskDependencyViewSet, basename='task-dependencies') # Dependencies under tasks
task_router.register(r'subtasks', TaskViewSet, basename='task-subtasks') # Subtasks under tasks


urlpatterns = [
    path('', include(router.urls)),
    path('projects/<int:project_pk>/', include(project_router.urls)), # Nested tasks under projects
    path('tasks/<int:task_pk>/', include(task_router.urls)), # Nested dependencies and subtasks under tasks
    path('users/me/assigned-tasks/', AssignedTaskListView.as_view(), name='assigned-tasks'), # List assigned tasks
    path('auth/login/', LoginView.as_view(), name='login-api'), # Login API endpoint
    path('auth/logout/', LogoutView.as_view(), name='logout-api'), 
    path('auth/register/', RegistrationView.as_view(), name='register-api'),
    path('tasks/<int:pk>/assign/', TaskViewSet.as_view({'patch': 'assign'}), name='task-assign'),
    path('projects/<int:pk>/schedule/', ProjectViewSet.as_view({'get': 'schedule'}), name='project-schedule'),

]

def urlp():
    return urlpatterns