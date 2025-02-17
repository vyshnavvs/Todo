from django.db import models
from django.conf import settings

class Project(models.Model):

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start_date = models.DateField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='created_projects', on_delete=models.CASCADE)

    def __str__(self):
        return self.title

class Task(models.Model):

    project = models.ForeignKey(Project, related_name='tasks', on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    duration_days = models.PositiveIntegerField(default=1) # Duration in days
    is_private = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='created_tasks', on_delete=models.CASCADE)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='assigned_tasks', on_delete=models.SET_NULL, null=True, blank=True) # Can be null if not assigned
    parent_task = models.ForeignKey('self', related_name='subtasks', on_delete=models.CASCADE, null=True, blank=True) # For subtasks
    is_completed = models.BooleanField(default=False)
    completion_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):

        if self.parent_task and self.parent_task.is_private:
            self.is_private = True  # Inherit privacy from parent
        super().save(*args, **kwargs)

    @property
    def is_main_task(self):

        return self.parent_task is None
    
    @classmethod
    def are_dependencies_met(cls, task):
        """
        Class method to check if dependencies for a task are met.
        Handles AND/OR logical conditions.
        """
        dependencies = task.dependencies.all() # Get dependencies for this task

        if not dependencies: # No dependencies, consider them met
            return True

        dependency_met_status = [] # List to store status of each dependency

        for dependency in dependencies:
            depends_on_task = dependency.depends_on_task

            # For now, we are only checking 'finish_to_start' and task completion
            if dependency.dependency_type == 'finish_to_start':
                dependency_met_status.append(depends_on_task.is_completed) # Check if 'depends_on' task is completed
            else:
                dependency_met_status.append(False) # Handle other dependency types (or default to False if not implemented yet)
                print(f"Warning: Dependency type '{dependency.dependency_type}' not fully implemented in dependency check.")

        logical_condition = dependency.logical_condition.upper() # Ensure case-insensitive comparison

        if logical_condition == 'AND':
            return all(dependency_met_status) # All dependencies must be met for AND
        elif logical_condition == 'OR':
            return any(dependency_met_status) # At least one dependency must be met for OR
        else:
            print(f"Warning: Logical condition '{dependency.logical_condition}' not recognized. Defaulting to NOT MET.")
            return False # Unknown logical condition, default to not met



class TaskDependency(models.Model):
    """Represents a dependency between tasks."""
    task = models.ForeignKey(Task, related_name='dependencies', on_delete=models.CASCADE)
    depends_on_task = models.ForeignKey(Task, related_name='dependent_tasks', on_delete=models.CASCADE)
    dependency_type = models.CharField(max_length=50, default='finish_to_start') # For future, e.g., start_to_start, finish_to_finish
    logical_condition = models.CharField(max_length=50, default='AND') # Future use if needed, currently focusing on sequential dependencies

    def __str__(self):
        return f"Dependency: {self.task.title} depends on {self.depends_on_task.title}"

    def clean(self):
        """Django model clean method to add custom validation."""
        if self.task.project != self.depends_on_task.project:
            raise ValidationError("Tasks in a dependency must belong to the same project.")
        if self.task == self.depends_on_task:
            raise ValidationError("Task cannot depend on itself.")
        if self.depends_on_task.parent_task and self.task.is_main_task:
            raise ValidationError("Main task cannot depend on a subtask directly. Dependencies can only be between tasks at the same level or between subtasks.")
        if self.task.parent_task and self.depends_on_task.is_main_task:
             raise ValidationError("Subtask cannot depend on a main task directly.")


from django.core.exceptions import ValidationError
from django.dispatch import receiver
from django.db.models.signals import pre_save

@receiver(pre_save, sender=Task)
def enforce_privacy_inheritance(sender, instance, **kwargs):
    """Signal handler to enforce privacy inheritance for subtasks."""
    if instance.parent_task and instance.parent_task.is_private and not instance.is_private:
        instance.is_private = True