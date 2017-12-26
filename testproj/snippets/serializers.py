from django.contrib.auth import get_user_model
from rest_framework import serializers

from snippets.models import Snippet, LANGUAGE_CHOICES, STYLE_CHOICES


class LanguageSerializer(serializers.Serializer):

    name = serializers.ChoiceField(
        choices=LANGUAGE_CHOICES, default='python', help_text='The name of the programming language')

    class Meta:
        ref_name = None


class ExampleProjectSerializer(serializers.Serializer):

    project_name = serializers.CharField(help_text='Name of the project')
    github_repo = serializers.CharField(required=True, help_text='Github repository of the project')

    class Meta:
        ref_name = 'Project'


class SnippetSerializer(serializers.Serializer):
    """SnippetSerializer classdoc

    create: docstring for create from serializer classdoc
    """
    id = serializers.IntegerField(read_only=True, help_text="id serializer help text")
    owner = serializers.PrimaryKeyRelatedField(
        queryset=get_user_model().objects.all(),
        default=serializers.CurrentUserDefault(),
        help_text="The ID of the user that created this snippet; if none is provided, "
                  "defaults to the currently logged in user."
    )
    owner_as_string = serializers.PrimaryKeyRelatedField(
        help_text="The ID of the user that created this snippet.",
        pk_field=serializers.CharField(help_text="this help text should not show up"),
        read_only=True,
        source='owner',
    )
    title = serializers.CharField(required=False, allow_blank=True, max_length=100)
    code = serializers.CharField(style={'base_template': 'textarea.html'})
    linenos = serializers.BooleanField(required=False)
    language = LanguageSerializer(help_text="Sample help text for language")
    styles = serializers.MultipleChoiceField(choices=STYLE_CHOICES, default=['friendly'])
    lines = serializers.ListField(child=serializers.IntegerField(), allow_empty=True, allow_null=True, required=False)
    example_projects = serializers.ListSerializer(child=ExampleProjectSerializer(), read_only=True)
    difficulty_factor = serializers.FloatField(help_text="this is here just to test FloatField",
                                               read_only=True, default=lambda: 6.9)

    def create(self, validated_data):
        """
        Create and return a new `Snippet` instance, given the validated data.
        """
        del validated_data['styles']
        del validated_data['lines']
        del validated_data['difficulty_factor']
        return Snippet.objects.create(**validated_data)

    def update(self, instance, validated_data):
        """
        Update and return an existing `Snippet` instance, given the validated data.
        """
        instance.title = validated_data.get('title', instance.title)
        instance.code = validated_data.get('code', instance.code)
        instance.linenos = validated_data.get('linenos', instance.linenos)
        instance.language = validated_data.get('language', instance.language)
        instance.style = validated_data.get('style', instance.style)
        instance.save()
        return instance
