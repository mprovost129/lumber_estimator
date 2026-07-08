import json

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from accounts.models import Account
from catalog.models import MaterialProduct
from estimating.models import Assembly

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
            'color': '#112233',
        }
        self.client.post(url, data=json.dumps(payload), content_type='application/json')

        payload['settings'] = {'stud_spacing_in': 24}
        self.client.post(url, data=json.dumps(payload), content_type='application/json')

        presets = ToolPreset.objects.filter(account=self.user.account, name='Exterior Wall')
        self.assertEqual(presets.count(), 1)
        self.assertEqual(presets.first().settings['stud_spacing_in'], 24)
        self.assertEqual(presets.first().color, '#112233')

    def test_saving_preset_stores_assembly(self):
        self.client.force_login(self.user)
        assembly = Assembly.objects.create(name='Preset Wall Assembly', tool_type='line')
        url = reverse('plans:presets')
        payload = {
            'name': 'Exterior Wall', 'tool_type': 'line',
            'material_id': self.material.id, 'assembly_id': assembly.id,
            'settings': {'stud_spacing_in': 16}, 'color': '#112233',
        }
        response = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['assembly_id'], assembly.id)

        preset = ToolPreset.objects.get(account=self.user.account, name='Exterior Wall')
        self.assertEqual(preset.assembly_id, assembly.id)

    def test_saving_preset_rejects_assembly_of_wrong_tool_type(self):
        self.client.force_login(self.user)
        area_assembly = Assembly.objects.create(name='Preset Area Assembly', tool_type='area')
        url = reverse('plans:presets')
        payload = {
            'name': 'Exterior Wall', 'tool_type': 'line',
            'material_id': self.material.id, 'assembly_id': area_assembly.id,
            'settings': {}, 'color': '#112233',
        }
        response = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ToolPreset.objects.filter(account=self.user.account, name='Exterior Wall').exists())

    def test_saving_preset_rejects_another_accounts_assembly(self):
        self.client.force_login(self.user)
        other_account = Account.objects.create(name='Other Preset Co')
        foreign_assembly = Assembly.objects.create(account=other_account, name='Foreign Wall Assembly', tool_type='line')
        url = reverse('plans:presets')
        payload = {
            'name': 'Exterior Wall', 'tool_type': 'line',
            'material_id': self.material.id, 'assembly_id': foreign_assembly.id,
            'settings': {}, 'color': '#112233',
        }
        response = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_list_presets_includes_assembly_and_favorite(self):
        self.client.force_login(self.user)
        assembly = Assembly.objects.create(name='List Wall Assembly', tool_type='line')
        ToolPreset.objects.create(
            account=self.user.account, tool_type='line', name='Exterior Wall',
            material=self.material, assembly=assembly, is_favorite=True,
        )
        response = self.client.get(reverse('plans:presets'), {'tool_type': 'line'})
        preset_data = response.json()['presets'][0]
        self.assertEqual(preset_data['assembly_id'], assembly.id)
        self.assertTrue(preset_data['is_favorite'])


class ToolPresetFavoriteToggleViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='favtoggle@example.com', password='testpass123')
        self.preset = ToolPreset.objects.create(
            account=self.user.account, tool_type='line', name='Exterior Wall',
        )

    def test_toggle_favorite_on_then_off(self):
        self.client.force_login(self.user)
        url = reverse('plans:preset-favorite', args=[self.preset.pk])

        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['is_favorite'])
        self.preset.refresh_from_db()
        self.assertTrue(self.preset.is_favorite)

        response = self.client.post(url)
        self.assertFalse(response.json()['is_favorite'])
        self.preset.refresh_from_db()
        self.assertFalse(self.preset.is_favorite)

    def test_cannot_toggle_another_accounts_preset(self):
        other_user = User.objects.create_user(email='favtoggle2@example.com', password='testpass123')
        self.client.force_login(other_user)
        url = reverse('plans:preset-favorite', args=[self.preset.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)
