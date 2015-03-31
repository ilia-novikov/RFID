$(document).ready(function () {
    initialize_datepicker();
    initialize_picker();
    disable_form_action();
    var name_field = $('#name');
    if (name_field.length) {
        name_field.focusout(function () {
            set_validation(name_field, is_not_empty(name_field), "Заполните имя пользователя");
        });
    }
    var card_field = $('#card');
    if (card_field.length) {
        card_field.focusout(function () {
            check_card(card_field);
        });
    }
    var expire_field = $('#expire');
    if (expire_field.length) {
        expire_field.focusout(function () {
            set_validation(expire_field, is_not_empty(expire_field), "Заполните дату окончания");
        });
    }
});

function initialize_datepicker() {
    var picker = $('#expire');
    if (!picker.length) return;
    picker.datepicker({
        format: "dd.mm.yyyy",
        weekStart: 1,
        startDate: "+1d",
        autoclose: true
    });
    picker.datepicker('setDate', '01.01.2020');
}

function initialize_picker() {
    var access_field = $('#access');
    if (!access_field.length) return;
    access_field.selectpicker();
}

function disable_form_action() {
    var form = $('form');
    if (!form.length) return;
    form.on("keyup keypress", function (e) {
        var code = e.keyCode || e.which;
        if (code == 13) {
            e.preventDefault();
            return false;
        }
    });
}

function is_not_empty(element) {
    return (element[0].value != undefined) && (element[0].value.trim() != '');
}

function is_number(element) {
    return !isNaN(parseFloat(element[0].value)) && isFinite(element[0].value);
}

function check_card(element) {
    var card = element[0].value;
    if (!is_not_empty(element)) {
        set_validation(element, false, "Заполните карту пользователя");
        return;
    }
    if (!is_number(element)) {
        set_validation(element, false, "Неверный формат карты");
        return;
    }
    request('validate', {'card': card}, function (data) {
        if (!data) {
            set_validation(element, false, "Ошибка запроса к серверу");
            return;
        }
        set_validation(element, jQuery.parseJSON(data['is_valid']), "Карта уже зарегистрирована");
    });
}

function set_validation(element, is_valid, message) {
    if (is_valid) {
        element.parent().removeClass('has-error');
        element.parent().addClass('has-success');
        element[0].setCustomValidity('');
    } else {
        element.parent().removeClass('has-success');
        element.parent().addClass('has-error');
        element[0].setCustomValidity(message);
    }
}

function request(method, params, callback) {
    var url;
    if (params) {
        url = '/request/' + method + '?' + jQuery.param(params);
    } else {
        url = '/request/' + method;
    }
    jQuery.ajax({
        url: url,
        success: function (data) {
            data = JSON.parse(data);
            if (data['error']) {
                console.log("Server side error: " + data['error']);
                callback(undefined);
                return;
            }
            if (data['success']) {
                callback(data);
                return;
            }
            console.log("Undefined response: " + data);
            callback(undefined);
        },
        error: function (data, status, error) {
            console.log("AJAX error: " + data.status);
            callback(undefined);
        }
    });
}