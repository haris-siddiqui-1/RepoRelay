"""
View handlers for GitHub Insights Dashboard web UI.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from dojo.models import Product_Type


@login_required
def github_insights_dashboard(request):
    """
    Render the GitHub Insights Dashboard page.

    This page provides an interactive dashboard for viewing repository insights
    with configurable widgets, charts, and filters.
    """
    # Get all product types for filter dropdown
    product_types = Product_Type.objects.all().order_by('name')

    context = {
        'product_types': product_types,
    }

    return render(request, 'dojo/github_insights_dashboard.html', context)
