# Generated manually to add signature support

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("api_testing", "0002_initial"),
    ]

    operations = [
        # 先创建 SignatureConfig 表（如果不存在）
        migrations.CreateModel(
            name='SignatureConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='配置名称')),
                ('description', models.TextField(blank=True, verbose_name='配置描述')),
                ('algorithm', models.CharField(max_length=50, verbose_name='签名算法', choices=[
                    ('MD5', 'MD5'),
                    ('SHA1', 'SHA1'),
                    ('SHA256', 'SHA256'),
                    ('SHA512', 'SHA512'),
                    ('HMAC-MD5', 'HMAC-MD5'),
                    ('HMAC-SHA1', 'HMAC-SHA1'),
                    ('HMAC-SHA256', 'HMAC-SHA256'),
                ])),
                ('secret_key', models.CharField(blank=True, max_length=500, null=True, verbose_name='密钥')),
                ('is_enabled', models.BooleanField(default=True, verbose_name='是否启用')),
                ('is_default', models.BooleanField(default=False, verbose_name='是否默认')),
                ('extra_params', models.JSONField(default=dict, verbose_name='额外参数')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='signature_configs', to='api_testing.apiproject', verbose_name='关联项目')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='创建者')),
            ],
            options={
                'db_table': 'signature_configs',
                'verbose_name': '签名配置',
                'verbose_name_plural': '签名配置',
                'ordering': ['-created_at'],
            },
        ),

        # 在 ApiRequest 表中添加签名相关字段
        migrations.AddField(
            model_name='apirequest',
            name='signature_config',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='requests',
                to='api_testing.signatureconfig',
                verbose_name='签名配置'
            ),
        ),

        migrations.AddField(
            model_name='apirequest',
            name='enable_signature',
            field=models.BooleanField(default=False, verbose_name='启用签名'),
        ),
    ]
