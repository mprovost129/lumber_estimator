import json

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from accounts.models import Account
from catalog.models import MaterialProduct

from .models import ToolPreset

User = get_user_model()


class ToolPresetModelTests(TestCase):
    def test_unique_preset_name_per_account_and_tool(self):
        account = Account.objects.create(name='Preset Co')
        ToolPreset.objects.create(account=account, tool_type='line', name='Exterior Wall')
        with self.assertRaises(IntegrityError), transaction.atomic():
            ToolPreset.objects.create(account=account, tool_type='line', name='Exterior Wall')


class ToolPresetViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='preset@example.com', password='testpass123')
        self.material = MaterialProduct.objects.create(
            name='Preset Material', input_type=MaterialProduct.InputType.FT,
        )

    def test_saving_same_name_updates_existing_preset(self):
        self.client.force_login(self.user)
        url = reverse('plans:presets')
        payload = {
            'name': 'Exterior Wall', 'tool_type': 'line',
            'material_id': self.material.id, 'settings': {'stud_spacing_in': 16},
        }
        self.client.post(url, data=json.dumps(payload), content_type='application/json')

        payload['settings'] = {'stud_spacing_in': 24}
        self.client.post(url, data=json.dumps(payload), content_type='application/json')

        presets = ToolPreset.objects.filter(account=self.user.account, name='Exterior Wall')
        self.assertEqual(presets.count(), 1)
        self.assertEqual(presets.first().settings['stud_spacing_in'], 24)
