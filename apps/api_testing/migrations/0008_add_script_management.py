# Generated migration for script management feature

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('api_testing', '0007_add_extra_params_in_sign'),
    ]

    operations = [
        # Create Script model
        migrations.CreateModel(
            name='Script',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='脚本名称')),
                ('description', models.TextField(blank=True, verbose_name='脚本描述')),
                ('script_type', models.CharField(
                    choices=[('python', 'Python'), ('javascript', 'JavaScript')],
                    default='python',
                    max_length=20,
                    verbose_name='脚本类型'
                )),
                ('content', models.TextField(verbose_name='脚本内容')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否激活')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('owner', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='scripts',
                    to='users.user',
                    verbose_name='创建者'
                )),
                ('project', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='scripts',
                    to='api_testing.apiproject',
                    verbose_name='所属项目'
                )),
            ],
            options={
                'verbose_name': '脚本',
                'verbose_name_plural': '脚本',
                'db_table': 'api_scripts',
                'ordering': ['-created_at'],
            },
        ),
        
        # Add fields to ApiRequest model
        migrations.AddField(
            model_name='apirequest',
            name='pre_request_script_ref',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='pre_request_requests',
                to='api_testing.script',
                verbose_name='前置脚本'
            ),
        ),
        migrations.AddField(
            model_name='apirequest',
            name='post_request_script_ref',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='post_request_requests',
                to='api_testing.script',
                verbose_name='后置脚本'
            ),
        ),
        migrations.AddField(
            model_name='apirequest',
            name='enable_pre_request_script',
            field=models.BooleanField(default=False, verbose_name='启用前置脚本'),
        ),
        migrations.AddField(
            model_name='apirequest',
            name='enable_post_request_script',
            field=models.BooleanField(default=False, verbose_name='启用后置脚本'),
        ),
        
        # Add unique constraint for Script
        migrations.AlterUniqueTogether(
            name='script',
            unique_together=[('project', 'name')],
        ),
    ]
