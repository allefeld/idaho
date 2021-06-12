// trigger server-side actions

function refresh() {
    // server-side refresh, then reload page
    fetch('?refresh').then(value => window.location.reload())
}

function open() {
    // server-side open folder
    fetch('?open')
}
