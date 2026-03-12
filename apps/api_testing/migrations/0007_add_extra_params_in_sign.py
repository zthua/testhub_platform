# Generated migration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api_testing', '0006_add_rsa_encrypt_public_key'),
    ]

    operations = [
        migrations.AddField(
            model_name='signatureconfig',
            name='extra_params_in_sign',
            field=models.BooleanField(
                default=False,
                verbose_name='额外参数参与签名',
                help_text='如果勾选，额外参数将参与签名计算；否则只对请求体进行签名'
            ),
        ),
    ]
