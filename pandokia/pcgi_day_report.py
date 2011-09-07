#
# pandokia - a test reporting and execution system
# Copyright 2009, 2010, 2011 Association of Universities for Research in Astronomy (AURA) 
#

#
import sys
import cgi
import re
import copy
import time

import pandokia.text_table as text_table
import urllib

import pandokia
pdk_db = pandokia.cfg.pdk_db

import pandokia.common as common

import pandokia.pcgi

######
#
# day_report.1
#   show a list of test_run values that we can make a day_report for
#
# CGI parameters:
#   test_run = wild card pattern for test_run
#

def rpt1(  ) :

    form = pandokia.pcgi.form

    if form.has_key("test_run") :
        test_run = form["test_run"].value
    else :
        test_run = '*'

    if test_run == '-me' :
        test_run = 'user_' + common.current_user() + '_*'

    my_run_prefix = 'user_' + common.current_user()

    admin = common.current_user() in common.cfg.admin_user_list

    # c = db.execute("SELECT DISTINCT test_run FROM result_scalar WHERE test_run GLOB ? ORDER BY test_run DESC ",( test_run,))
    where_str, where_dict = pdk_db.where_dict( [ ( 'test_run', test_run ) ] )
    sql = "SELECT test_run, valuable, record_count, note FROM distinct_test_run %s ORDER BY test_run DESC "%where_str
    c = pdk_db.execute( sql, where_dict)

    table = text_table.text_table()
    table.define_column('addval',   showname='')
    table.define_column('run',      showname='test_run')
    table.define_column('tree',     showname='')
    table.define_column('del',      showname='')
    table.define_column('count',    showname='records')
    table.define_column('note',     showname='note')


    # query parameters for various links

    # link to day_report
    # link to tree walk of test run
    tquery = { 'project' : '*', 'host' : '*' }

    # link to declare a run as valuable
    vquery = { 'valuable_run' : 1 }

    # link to update the count in a test run
    cquery = { }


    row = 0
    for x, val, record_count, note in c :
        if x is None :
            continue
        tquery["test_run"] = x
        vquery["test_run"] = x
        cquery["count_run"] = x

        # mark as valuable:
        # https://ssb.stsci.edu/pandokia/c41.cgi?query=action&test_run=daily_2011-08-24&valuable_run=1
        table.set_value(row, 'addval', html='<a href="%s">!</a>&nbsp;&nbsp;&nbsp;' % common.selflink(vquery,"action") )

        table.set_value(row, 'run', text=x, link=common.selflink(tquery,"day_report.2") )
        table.set_value(row, 'tree', text='(tree display)', link=common.selflink(tquery,"treewalk") )
        if val == '0' :
            if x.startswith(my_run_prefix) :
                table.set_value(row, 'del', text='(delete)', link=common.selflink(tquery,"delete_run.ays") )
            else :
                table.set_value(row, 'del', text='(delete)', html='<font color=gray>(delete)</font>', link=common.selflink(tquery,"delete_run.ays") )
        else :
            table.set_value(row, 'del', text='(valuable)' )

        if note is None :
            table.set_value(row, 'note', text='')
        else :
            table.set_value(row, 'note', text=note)


        # update the count field 
        # https://ssb.stsci.edu/pandokia/c41.cgi?query=action&count_run=daily_2011-08-24

        update_count = common.selflink(cquery,'action')
        if record_count is None or record_count <= 0 :
            record_count = '&nbsp;'
        table.set_value(row, 'count', html=str(record_count), link=update_count )

        row = row + 1


    if pandokia.pcgi.output_format == 'html' :
        sys.stdout.write(common.cgi_header_html)
        sys.stdout.write(common.page_header())
        sys.stdout.write('<h2>%s</h2>'%cgi.escape(test_run))
        sys.stdout.write(table.get_html(headings=1))
        sys.stdout.write("<br>Click on the ! to mark a test run as too valuable to delete\n")
        sys.stdout.write("<br>Click on record count to check the count and update it\n")
    elif pandokia.pcgi.output_format == 'csv' :
        sys.stdout.write(common.cgi_header_csv)
        sys.stdout.write(table.get_csv())

    sys.stdout.flush()

    return

######
#
# day_report.2
#   show the actual day report: 
#       for each project show a table containing pass/fail/error for each host
#
# parameters:
#   test_run = name of test run to show data for
#       no wild cards permitted, but we allow special names
#

def rpt2( ) :

    form = pandokia.pcgi.form

    if form.has_key("test_run") :
        test_run = form["test_run"].value
    else :
        # no parameter?  I think somebody is messing with us...
        # no matter - just give them a the list of all the test_runs
        rpt1()
        return

    #
    test_run = common.find_test_run(test_run)

    # create list of projects
    projects = None
    host = None
    context = None

    if form.has_key("project") :
        projects = form.getlist("project")

    if form.has_key("host") :
       host = form.getlist("host")

    if form.has_key("context") :
       context = form.getlist("context")

    # create the actual table
    [ table, projects ] = gen_daily_table( test_run, projects, context, host )

# # # # # # # # # # 
    if pandokia.pcgi.output_format == 'html' :
        
        header = "<h1>"+cgi.escape(test_run)+"</h1>\n"

        if test_run.startswith('daily_') :
            # 
            # If we have a daily run, create a special header.

            # show the day of the week, if we can
            try :
                import datetime
                t = test_run[len('daily_'):]
                t = t.split('-')
                t = datetime.date(int(t[0]),int(t[1]),int(t[2]))
                t = t.strftime("%A")
                header = header+ "<h2>"+str(t)+"</h2>"
            except :
                pass

            # Include links to the previous / next day's daily run.
            # It is not worth the cost of looking in the database to make sure the day that
            # we link to really exists.  It almost always does, and if it doesn't, the user
            # will find out soon enough.
            # 

            prev = common.previous_daily( test_run )
            back = common.self_href( query_dict = {  'test_run' : prev } , linkmode='day_report.2', text=prev )
            header = header + '( prev ' + back

            latest = common.find_test_run('daily_latest') 
            if test_run != latest :
                next = common.next_daily( test_run )
                header = header + " / next " + common.self_href( query_dict={  'test_run' : next } , linkmode='day_report.2', text=next )
                if next != latest :
                    header = header + " / latest " + common.self_href( query_dict={  'test_run' : latest } , linkmode='day_report.2', text=latest )

            header = header + ' )<p>\n'

        c = pdk_db.execute("SELECT note, valuable FROM distinct_test_run WHERE test_run = :1",(test_run,))
        note, valuable = c.fetchone()
        if note is None :
            note = ''
        if valuable is None :
            valuable = 0
        else :
            valuable = int(valuable)

        header = header + '<p><form action=%s>\nNote: <input type=text name=note value="%s" width=%d>\n<input type=hidden name=test_run value="%s">\n<input type=hidden name=query value=action></form></p>'%( common.get_cgi_name(), note, len(note)+20, test_run )

        if valuable :
            header = header + '<p>valuable '
        else :
            header = header + '<p>not valuable '
        header = header + '(<a href=%s>change</a>)'%(common.selflink( {'test_run':test_run, 'valuable_run': int(not valuable) }, linkmode='action' ))

        sys.stdout.write(common.cgi_header_html)
        sys.stdout.write(common.page_header())
        sys.stdout.write(header)
        sys.stdout.write(table.get_html(headings=0))
    elif pandokia.pcgi.output_format == 'csv' :
        sys.stdout.write(common.cgi_header_csv)
        sys.stdout.write(table.get_csv())


#   #   #   #   #   #   #   #   #   #


def gen_daily_table( test_run, projects, query_context, query_host ) :

    # convert special names, e.g. daily_latest to the name of the latest daily_*
    test_run = common.find_test_run(test_run)

    # this is the skeleton of the cgi queries for various links
    query = { "test_run" : test_run }

    # This is a single table for all projects, because we want the
    # pass/fail/error columns to be aligned from one to the next
    #
    table = text_table.text_table()

    # The texttable object doesn't understand colspans, but we hack a
    # colspan into it anyway.  Thee result is ugly if you have borders.

    table.set_html_table_attributes("cellpadding=2 ")

    status_types = common.cfg.statuses

    row = 0 
    table.define_column("host")
    table.define_column("context")
    table.define_column("os")
    table.define_column("total")
    for x in status_types :
        table.define_column(x)
    table.define_column("note")

#   #   #   #   #   #   #   #   #   #
    # loop across hosts
    prev_project = None

    all_sum = { 'total' : 0 }
    for status in status_types :
        all_sum[status] = 0

    n_cols = 3

    hc_where, hc_where_dict = pdk_db.where_dict( [ ( 'test_run', test_run ), ('project', projects), ( 'context', query_context ), ('host', query_host) ]  )
    c = pdk_db.execute("SELECT DISTINCT project, host, context FROM result_scalar %s ORDER BY project, host, context " % hc_where, hc_where_dict )
    for project, host, context in c :

        if project != prev_project :

            table.set_value(row,0,"")
            row = row + 1

            prev_project = project

            # values common to all the links we will write in this pass through the loop
            query["project"] = project
            query["host"] = "%"

            # this link text is common to all the links for this project
            link = common.selflink(query_dict = query, linkmode="treewalk" )

            # the heading for a project subsection of the table
            table.set_value(row, 0, text=project, html="<hr><big><strong><b>"+project+"</b></strong></big>", link=link)
            n_cols = 3 + len(status_types) + 1
            table.set_html_cell_attributes(row,0,"colspan=%d"%n_cols)
            row += 1

            # the column headings for this project's part of the table
            insert_col_headings( table, row, link )
            row += 1

            # This will be the sum of all the tests in a particular project.
            # It comes just under the headers for the project, but we don't
            # know the values until the end.
            project_sum = { 'total' : 0 }
            for status in status_types :
                project_sum[status] = 0

            project_sum_row = row
            row += 1

            prev_host = None

        query["host"] = host

        link = common.selflink(query_dict = query, linkmode="treewalk" )

        if host != prev_host :
            table.set_value(row,0,    text=host,        link=link)
            prev_host = host

        query['context'] = context
        link=common.selflink(query_dict = query, linkmode="treewalk" )
        del query['context']

        table.set_value(row,1,    text=context,        link = link)
        table.set_value(row,2,    text=pandokia.cfg.os_info.get(host,'?') )
        total_results = 0
        missing_count = 0
        for status in status_types :
            c1 = pdk_db.execute("SELECT COUNT(*) FROM result_scalar WHERE  test_run = :1 AND project = :2 AND host = :3 AND status = :4 AND context = :5",
                ( test_run, project, host, status, context ) )
            (x,) = c1.fetchone()
            total_results += x
            project_sum[status] += x
            all_sum[status] += x
            table.set_value(row, status, text=str(x), link = link + "&status="+status )
            table.set_html_cell_attributes(row, status, 'align="right"' )

            if x == 'M' :
                missing_count = x

        project_sum['total'] += total_results
        all_sum['total'] += total_results

        if 'M' in status_types :
            if missing_count == total_results :
                # if it equals the total, then everything is missing; we make a note of that
                table.set_value(row, 'note', 'all')
            elif missing_count != 0 :
                # if it is not 0, then we have a problem
                table.set_value(row, 'note', 'some')

        table.set_value(row, 'total', text=str(total_results), link=link )
        table.set_html_cell_attributes(row, 'total', 'align="right"' )

        row = row + 1

        for status in status_types :
            table.set_value(project_sum_row, status, project_sum[status] )
            table.set_html_cell_attributes(project_sum_row, status, 'align="right"' )

        table.set_value(project_sum_row, 'total', project_sum['total'] )
        table.set_html_cell_attributes(project_sum_row, 'total', 'align="right"' )

        # insert this blank line between projects - keeps the headings away from the previous row
        table.set_value(row,0,"")

    # insert a total for everything
    row += 1
    table.set_value(row, 0, html='<hr>')
    table.set_html_cell_attributes(row,0,"colspan=%d"%n_cols)

    row = row + 1
    insert_col_headings( table, row, None )

    row = row + 1
    total_row = row

    query['host']  = '*'
    query['project'] = projects
    query['host'] = query_host
    query['context'] = query_context

    table.set_value(total_row, 'total', text=str(all_sum['total']), 
        link = common.selflink(query_dict = query, linkmode="treewalk" )
        )
    table.set_html_cell_attributes(row, 'total', 'align="right"' )
    
    for status in status_types :
        query['status'] = status
        table.set_value(total_row, status, all_sum[status] ,
            link = common.selflink(query_dict = query, linkmode="treewalk" )
            )
        table.set_html_cell_attributes(total_row, status, 'align="right"' )

    return [ table, projects ]


#
# 
#
def insert_col_headings( table, row, link ) :
    table.set_value(row, "total", text="total", link=link )
    table.set_html_cell_attributes(row, 'total', 'align="right"' )
    xl = None
    for x in common.cfg.statuses :
        xn = common.cfg.status_names[x]
        if link :
            xl = link + '&status='+x 
        table.set_value(row, x, text=xn, link = xl )
        table.set_html_cell_attributes(row, x, 'align="right"' )
    table.set_value(row, "note", text="" )  # no heading for this one

