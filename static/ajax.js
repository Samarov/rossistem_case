$(document).on('change', 'select#spec_id', function() {
	var selected = $(this).val();
    $.ajax({
        url: '/is_ajax_1',
        type: 'POST',
		cache: false,
        data: {
            spec_id: selected
        },
        success: function(data) {
            $('select#skil_id').html(data);
        }
    });
});
$(document).on('change', 'select#public_id', function() {
	var selected = $(this).val();
    $.ajax({
        url: '/is_ajax_2',
        type: 'POST',
		cache: false,
        data: {
            public_id: selected
        },
        success: function(data) {
            $('textarea#skil_public').text(data);
        }
    });
});
$('table#edit_table').on('click', 'td', function() {
	var td_text = $(this).text();
	var td_hidden = $(this).attr("id");
	$('input#input_correct').val(td_text);
	$('input#input_hidden').val(td_hidden);
});