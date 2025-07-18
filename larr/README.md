# Land Acquisition and Rehabilitation (LARR) Module

A comprehensive Odoo module for managing Land Acquisition and Rehabilitation processes, designed to streamline and automate the complex workflows involved in land acquisition projects.

## Features

### 🏗️ Project Management
- **Project Creation & Tracking**: Create and manage LARR projects with detailed information
- **Progress Monitoring**: Real-time progress tracking with visual indicators
- **Team Management**: Assign project managers and team members
- **Cost Estimation**: Track estimated costs and actual expenditures

### 🏞️ Land Acquisition
- **Acquisition Process**: Complete workflow from survey to possession
- **Land Details**: Comprehensive land information including area, type, and ownership
- **Acquisition Types**: Support for voluntary, compulsory, and negotiated acquisitions
- **Status Tracking**: Multi-stage status management (Draft → Survey → Negotiation → Agreement → Possession → Completed)

### 💰 Compensation Management
- **Multiple Compensation Types**: Land, structure, crop, and livelihood compensation
- **Payment Tracking**: Monitor payment status and methods
- **Bulk Operations**: Process multiple compensations simultaneously
- **Financial Reporting**: Detailed financial summaries and reports

### 🏠 Rehabilitation & Resettlement
- **Affected Person Management**: Track affected families and their details
- **Rehabilitation Plans**: Land-for-land, house-for-house, monetary, and employment options
- **Progress Monitoring**: Track rehabilitation implementation stages
- **Documentation**: Complete documentation of rehabilitation processes

### 👥 Stakeholder Management
- **Stakeholder Identification**: Categorize and manage different types of stakeholders
- **Engagement Tracking**: Monitor engagement levels and concerns
- **Communication**: Track stakeholder communications and mitigation plans
- **Risk Management**: Identify and address stakeholder concerns

### 📄 Document Management
- **Document Types**: Support for various document types (land records, agreements, reports)
- **Version Control**: Track document versions and approvals
- **Expiry Management**: Automatic expiry notifications
- **Digital Storage**: Secure document storage and retrieval

### 📊 Analytics & Reporting
- **Dashboard**: Real-time dashboard with key metrics
- **Custom Reports**: Generate various types of reports
- **Progress Analytics**: Visual progress tracking and analytics
- **Financial Summaries**: Comprehensive financial reporting

## Installation

1. **Copy the Module**: Place the `larr` folder in your Odoo addons directory
2. **Update Module List**: Go to Apps → Update Apps List
3. **Install Module**: Search for "Land Acquisition and Rehabilitation" and install
4. **Configure Security**: Assign users to appropriate LARR groups

## User Groups

### LARR User
- Read access to all LARR records
- Basic viewing and reporting capabilities

### LARR Manager
- Create, edit, and manage LARR records
- Approve compensations and documents
- Generate reports and analytics

### LARR Administrator
- Full access to all LARR functionality
- Delete records and manage system settings
- Configure workflows and security

## Models

### Core Models

1. **LARR Project** (`larr.project`)
   - Main project entity
   - Contains project details, team, and progress tracking

2. **Land Acquisition** (`larr.land.acquisition`)
   - Individual land acquisition records
   - Links to projects and land owners
   - Tracks acquisition process and compensation

3. **Rehabilitation** (`larr.rehabilitation`)
   - Rehabilitation and resettlement records
   - Tracks affected persons and rehabilitation plans

4. **Compensation** (`larr.compensation`)
   - Compensation payment records
   - Links to acquisitions and beneficiaries

5. **Stakeholder** (`larr.stakeholder`)
   - Stakeholder management
   - Tracks engagement and concerns

6. **Document** (`larr.document`)
   - Document management
   - Tracks document lifecycle and approvals

### Dashboard Models

1. **LARR Dashboard** (`larr.dashboard`)
   - Main dashboard view
   - Aggregated statistics and metrics

2. **Project Dashboard** (`larr.project.dashboard`)
   - Project-specific analytics
   - Progress tracking and reporting

### Wizard Models

1. **Compensation Wizard** (`larr.compensation.wizard`)
   - Single compensation creation
   - Automated beneficiary selection

2. **Bulk Compensation Wizard** (`larr.bulk.compensation.wizard`)
   - Multiple compensation processing
   - Batch operations for efficiency

3. **Report Wizard** (`larr.report.wizard`)
   - Custom report generation
   - Multiple report types and filters

## Workflows

### Land Acquisition Workflow
1. **Draft**: Initial project setup
2. **Survey**: Land survey and assessment
3. **Negotiation**: Compensation negotiations
4. **Agreement**: Agreement signing
5. **Possession**: Land possession
6. **Completed**: Final completion

### Rehabilitation Workflow
1. **Draft**: Initial rehabilitation planning
2. **Survey**: Affected person survey
3. **Planning**: Rehabilitation plan development
4. **Implementation**: Plan implementation
5. **Completed**: Rehabilitation completion

### Compensation Workflow
1. **Draft**: Initial compensation record
2. **Approved**: Compensation approval
3. **Paid**: Payment completion
4. **Cancelled**: Cancellation (if applicable)

## API Endpoints

The module provides REST API endpoints for integration:

- `GET /larr/api/projects` - Get all projects
- `GET /larr/api/acquisitions` - Get land acquisitions
- `GET /larr/api/compensations` - Get compensations
- `GET /larr/api/dashboard` - Get dashboard data
- `GET /larr/api/project/{id}/dashboard` - Get project-specific dashboard

## Reports

### Available Reports
1. **Project Summary Report** - Overview of all projects
2. **Acquisition Status Report** - Land acquisition status
3. **Compensation Summary Report** - Compensation details
4. **Rehabilitation Status Report** - Rehabilitation progress
5. **Stakeholder Analysis Report** - Stakeholder information
6. **Financial Summary Report** - Financial overview

## Configuration

### Sequences
- Project sequences: `LARR/PROJ/YYYY/XXXXX`
- Acquisition sequences: `LARR/ACQ/YYYY/XXXXX`
- Rehabilitation sequences: `LARR/REHAB/YYYY/XXXXX`
- Compensation sequences: `LARR/COMP/YYYY/XXXXX`
- Document sequences: `LARR/DOC/YYYY/XXXXX`

### Cron Jobs
- **Document Expiry Check**: Daily check for expired documents
- **Notification System**: Automated notifications for key events

## Customization

### Adding Custom Fields
```python
# In your custom module
from odoo import fields, models

class LARRProject(models.Model):
    _inherit = 'larr.project'
    
    custom_field = fields.Char('Custom Field')
```

### Custom Workflows
```python
# Add custom states
state = fields.Selection([
    ('draft', 'Draft'),
    ('custom_state', 'Custom State'),
    ('completed', 'Completed')
], default='draft')
```

## Dependencies

- **base**: Core Odoo functionality
- **mail**: Messaging and notifications
- **hr**: Employee management
- **project**: Project management
- **account**: Financial management
- **web**: Web interface
- **portal**: Portal access

## Support

For support and customization requests, please contact:
- **Email**: support@bharatddn.com
- **Website**: https://www.bharatddn.com

## License

This module is licensed under LGPL-3.

## Version History

### v1.0.0 (Current)
- Initial release
- Complete LARR workflow management
- Dashboard and reporting
- API endpoints
- Security and access control

## Contributing

We welcome contributions! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Roadmap

### Upcoming Features
- **Mobile App**: Mobile application for field operations
- **GIS Integration**: Geographic Information System integration
- **Advanced Analytics**: Machine learning-based analytics
- **Multi-language Support**: Support for multiple languages
- **Workflow Automation**: Advanced workflow automation
- **Integration APIs**: Third-party system integrations

---

**Developed by Bharat DDN** 