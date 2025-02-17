from rest_framework import serializers
from .models import Project, Task, TaskDependency
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User  # Or your custom user model
from django.contrib.auth.password_validation import validate_password
from django.core import exceptions

class RegistrationSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password]) # Password validation
    password2 = serializers.CharField(write_only=True, required=True) # Password confirmation
    email = serializers.EmailField(required=True)
    first_name = serializers.CharField(required=False, allow_blank=True) # Optional
    last_name = serializers.CharField(required=False, allow_blank=True)  # Optional


    class Meta:
        # No Meta class needed for Serializer, but can add if required
        pass

    def validate(self, data):
        """
        Check if passwords match and if username/email are unique.
        """
        if data['password'] != data['password2']:
            raise serializers.ValidationError({"password": "Passwords must match."})

        if User.objects.filter(username=data['username']).exists():
            raise serializers.ValidationError({"username": "Username already taken."})

        if User.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError({"email": "Email address already in use."})

        return data

    def create(self, validated_data):
        """
        Create a new user.
        """
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'], # create_user handles password hashing
            first_name=validated_data.get('first_name', ''), # Use .get() with default for optional fields
            last_name=validated_data.get('last_name', '')   # Use .get() with default for optional fields
        )
        return user



User = get_user_model()



class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name') # Include fields as needed


class ProjectSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True) # Display creator details

    class Meta:
        model = Project
        fields = ('id', 'title', 'description', 'start_date', 'created_by')
        read_only_fields = ('id', 'created_by') # created_by is set on server-side


class TaskSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all()) # Accept project ID for creation
    created_by = UserSerializer(read_only=True)
    assigned_to = UserSerializer(read_only=True) # Display assigned user details, make it writable if assignment is needed via API
    parent_task = serializers.PrimaryKeyRelatedField(queryset=Task.objects.all(), required=False, allow_null=True) # Allow null for main tasks

    class Meta:
        model = Task
        fields = ('id', 'project', 'title', 'description', 'duration_days', 'is_private', 'created_by', 'assigned_to', 'parent_task', 'is_completed', 'completion_date', 'is_main_task')
        read_only_fields = ('id', 'created_by', 'is_completed', 'completion_date', 'is_main_task') # Server-managed fields
    


class TaskDependencySerializer(serializers.ModelSerializer):
    task = serializers.PrimaryKeyRelatedField(queryset=Task.objects.all())
    depends_on_task = serializers.PrimaryKeyRelatedField(queryset=Task.objects.all())

    class Meta:
        model = TaskDependency
        fields = ('id', 'task', 'depends_on_task', 'dependency_type', 'logical_condition')
        read_only_fields = ('id',)

class TaskListSerializer(serializers.ModelSerializer): # For listing tasks with assigned user details
    assigned_to = UserSerializer(read_only=True)
    class Meta:
        model = Task
        fields = ('id', 'title', 'description', 'duration_days', 'is_private', 'assigned_to', 'is_completed', 'completion_date', 'is_main_task')

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    
class TaskAssignmentSerializer(serializers.Serializer):
    assigned_to_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=True) # Accept User ID for assignment