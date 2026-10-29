/* global gettext, horizon */
(function ($) {
  'use strict';

  horizon.addInitFunction(function () {
    $('[data-orbit-live]').each(function () {
      var $root = $(this);
      var $content = $root.find('.orbit-live-content');
      var $status = $root.find('.orbit-live-status');
      var timer;
      var request;
      var stopped = false;
      var pendingRefresh = false;
      var lastMarkup;

      function showStatus(message, failed, login) {
        $status.toggleClass('text-muted', !failed)
          .toggleClass('alert alert-warning', failed);
        $status.find('.orbit-live-message').text(message);
        $status.find('.orbit-live-login').prop('hidden', !login);
      }

      function unavailable(status) {
        var message = gettext('Unable to update. Displayed data may be out of date; retrying automatically.');
        if (status === 401) {
          message = gettext('Your session has expired. Sign in again to resume automatic updates.');
        } else if (status === 403) {
          message = gettext('Access denied. Displayed data may be out of date.');
        } else if (status === 404) {
          message = gettext('This orb is no longer available. Displayed data may be out of date.');
        }
        showStatus(message, true, status === 401);
      }

      function update(html) {
        var $next = $('<div>').append($.parseHTML(html));
        var $table = $content.find('table.datatable');
        if ($table.length) {
          var $nextTable = $next.find('table.datatable');
          var markup = $nextTable.find('tbody').html() + $nextTable.find('tfoot').html();
          if (markup !== lastMarkup) {
            $table.find('tbody').replaceWith($nextTable.find('tbody'));
            $table.find('tfoot').remove();
            $table.append($nextTable.find('tfoot'));
            if ($table[0].config) {
              $table.trigger('update');
            } else {
              horizon.datatables.set_table_sorting($content);
            }
            horizon.datatables.qs[$table.attr('id')].cache();
            lastMarkup = markup;
          }
        } else if (html !== lastMarkup) {
          $content.empty().append($next.contents());
          lastMarkup = html;
        }
        showStatus(gettext('Updates automatically every 5 seconds.'), false, false);
      }

      function schedule() {
        if (!stopped && !document.hidden) {
          timer = window.setTimeout(refresh, 5000);
        }
      }

      function refresh() {
        window.clearTimeout(timer);
        if (stopped || document.hidden || request) {
          return;
        }
        request = $.ajax({
          url: $root.attr('data-url'),
          data: {live: '1'},
          dataType: 'json',
          cache: false,
          global: false,
          timeout: 35000
        }).done(function (data) {
          if (pendingRefresh) {
            return;
          }
          try {
            if (data && typeof data.html === 'string') {
              update(data.html);
            } else {
              unavailable();
            }
          } catch (error) {
            unavailable();
          }
        }).fail(function (xhr) {
          if (!stopped) {
            unavailable(xhr.status);
          }
        }).always(function () {
          request = null;
          if (pendingRefresh) {
            pendingRefresh = false;
            refresh();
          } else {
            schedule();
          }
        });
      }

      document.addEventListener('visibilitychange', function () {
        window.clearTimeout(timer);
        if (!document.hidden) {
          if (request) {
            pendingRefresh = true;
          } else {
            refresh();
          }
        }
      });
      window.addEventListener('pagehide', function () {
        stopped = true;
        window.clearTimeout(timer);
        if (request) {
          request.abort();
        }
      });
      window.addEventListener('pageshow', function (event) {
        if (event.persisted) {
          stopped = false;
          refresh();
        }
      });
      schedule();
    });
  });
}(jQuery));
