window.addEvent('domready', function() {
	'use strict';

	var groupSelects = $$('.hidden');
	var entitiesSelect = $('entities');
	var entityOptions = entitiesSelect.getChildren('option');
	var currentGroup = null;

	function showGroup(groupId) {
		groupSelects.addClass('hidden');

		var groupSelect = $('group_' + groupId);
		var members = {};
		groupSelect.getChildren('option').each(function(option) {
			members[option.value] = true;
		});
		entitiesSelect.empty();
		entityOptions.each(function(entity) {
			if (!(entity.value in members)) {
				entitiesSelect.grab(entity);
			}
		});

		groupSelect.removeClass('hidden');
		currentGroup = groupSelect;
	}
	$('group').addEvent('change', function(e) {
		var groupId = e.target.value;
		showGroup(groupId);
	});
	showGroup($('group').value);

	function moveOptions(from, to) {
		var selectedEntities = Array.slice(from.selectedOptions);
		selectedEntities.each(function(o) {
			to.grab(o);
		});
	}
	$('add').addEvent('click', function(e) {
		e.preventDefault();
		moveOptions(entitiesSelect, currentGroup);
	});
	$('remove').addEvent('click', function(e) {
		e.preventDefault();
		moveOptions(currentGroup, entitiesSelect);
	});

	$('form').addEvent('submit', function(e) {
		currentGroup.set('name', 'entities');
		Array.map(currentGroup, function(o) {
			o.set('selected', true);
		});
	});
});
